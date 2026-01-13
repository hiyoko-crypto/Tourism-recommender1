import pandas as pd
import numpy as np

def minmax(s: pd.Series):
    s = s.astype(float)
    if s.max() == s.min():
        return pd.Series(np.ones(len(s)), index=s.index)
    return (s - s.min()) / (s.max() - s.min())

import pandas as pd
import numpy as np

def minmax(s: pd.Series):
    s = s.astype(float)
    if s.max() == s.min():
        return pd.Series(np.ones(len(s)), index=s.index)
    return (s - s.min()) / (s.max() - s.min())

def compute_user_preference(visited_spots, spot_feedback, df, selected_viewpoints):
    """
    Embedding 前提のユーザ嗜好推定
    df: スポット × 観点 類似度（横持ち）
    """

    viewpoint_cols = [c for c in df.columns if c != "スポット"]

    # ============================
    # 方法1：ユーザが選んだ観点 → 回数 × 0.05
    # ============================
    # 観点の出現回数をカウント
    viewpoint_count = {}

    for spot in visited_spots:
        for vp in spot_feedback[spot]["viewpoints"]:
            viewpoint_count[vp] = viewpoint_count.get(vp, 0) + 1

    # 観点ごとに「回数 × 0.05」を加点
    small_bonus = 0.05
    dup_scores = []
    for vp in viewpoint_cols:
        count = viewpoint_count.get(vp, 0)
        dup_scores.append({
            "観点": vp,
            "方法1スコア": count * small_bonus
        })

    df_dup = pd.DataFrame(dup_scores)

    # ============================
    # 方法2：訪問スポットの観点スコア合計
    # ============================
    df_visited = df[df["スポット"].isin(visited_spots)].copy()

    weighted_scores = []
    for vp in viewpoint_cols:
        total = df_visited[vp].sum()
        weighted_scores.append({
            "観点": vp,
            "方法2スコア": total
        })

    df_weighted = pd.DataFrame(weighted_scores)

    # ============================
    # 統合（方法1 + 方法2）
    # ============================
    summary = df_dup.merge(df_weighted, on="観点", how="outer").fillna(0)

    summary["方法2_norm"] = minmax(summary["方法2スコア"])

    summary["総合スコア"] = summary["方法1スコア"] + summary["方法2_norm"]

    summary = summary.sort_values("総合スコア", ascending=False)
    summary["興味あり"] = summary["観点"].apply(lambda x: 1 if x in selected_viewpoints else 0)

    return summary

def recommend_spots(user_pref_df, spot_scores, top_k=5):
    """ 
    user_pref_df: compute_user_preference の結果（観点 × 総合スコア） 
    spot_scores: スポット × 観点 の DataFrame 
    top_k: 5 or 10 
    use_aspect: True → 観点スコアを使う / False → 観点スコアを使わない 
    """

    # ① 観点を順位付け（高いほど上位）
    user_pref_df = user_pref_df.sort_values("総合スコア", ascending=False).reset_index(drop=True)

    # ② 順位に応じて重みをつける（例：1位=1.0, 2位=0.9, 3位=0.8 ...）
    base_weight = 1.0
    decay = 0.1  # 順位が1つ下がるごとに -0.1

    weights = []
    for i, row in user_pref_df.iterrows():
        weight = max(base_weight - decay * i, 0)  # 0未満にならないように
        weights.append(weight)

    user_pref_df["順位重み"] = weights

    # ③ 観点を index にして重みベクトルを作る
    weight_vec = user_pref_df.set_index("観点")["順位重み"]

    # ④ スポットごとにスコア計算（重み × 観点スコア の内積）
    results = []
    for spot, row in spot_scores.set_index("スポット").iterrows():
        score = (weight_vec * row).sum()
        results.append({"スポット": spot, "スコア": score})

    df_rec = pd.DataFrame(results).sort_values("スコア", ascending=False)
    return df_rec.head(10)
