import pandas as pd
import numpy as np

# ============================
# min-max 正規化（方法2用）
# ============================
def minmax(s: pd.Series):
    s = s.astype(float)
    if s.max() == s.min():
        return pd.Series(np.ones(len(s)), index=s.index)
    return (s - s.min()) / (s.max() - s.min())


# ============================
# ユーザー嗜好推定
# ============================
from collections import defaultdict
import pandas as pd
import numpy as np
def compute_user_preference(
    visited_spots,
    spot_feedback,
    df,
    selected_viewpoints,
    top_k
):
    viewpoint_cols = [c for c in df.columns if c != "スポット"]

    # ============================
    # 観点ごとに min-max 正規化
    # ============================
    df_norm = df.copy()
    for col in viewpoint_cols:
        vals = df[col].astype(float)
        if vals.max() == vals.min():
            df_norm[col] = 0.5
        else:
            df_norm[col] = (vals - vals.min()) / (vals.max() - vals.min())

    # ============================
    # 観点ランキング作成
    # ============================
    aspect_scores = defaultdict(float)
    boost_rate = 1.2

    for spot in visited_spots:
        row = df_norm[df_norm["スポット"] == spot].iloc[0]

        # ★ 各観光地の top-5 観点だけを使う
        top5 = row[viewpoint_cols].sort_values(ascending=False).head(5).index

        good_viewpoints = spot_feedback[spot]["viewpoints"]

        for v in top5:
            score = row[v]

            # ★ top-5 の中で「良かった観点」だけ 1.2 倍
            if v in good_viewpoints:
                score *= boost_rate

            aspect_scores[v] += score

    # ============================
    # 正規化（線形）
    # ============================
    aspect_scores = pd.Series(aspect_scores)
    weights = aspect_scores / aspect_scores.sum()

    # ============================
    # 観点ランキングの top-k
    # ============================
    topk_viewpoints = (
        weights.sort_values(ascending=False)
        .head(top_k)
        .index
        .tolist()
    )

    # ============================
    # UI / ログ用
    # ============================
    result = pd.DataFrame({
        "観点": weights.index,
        "総合スコア": weights.values,
        "興味あり": [1 if v in selected_viewpoints else 0 for v in weights.index]
    }).sort_values("総合スコア", ascending=False).reset_index(drop=True)

    return result, topk_viewpoints



# ============================
# スポット推薦
# ============================
def recommend_spots(
    user_pref_df,
    spot_scores,
    condition,
    selected_viewpoints,
    top_k=5
):
    viewpoint_cols = [c for c in spot_scores.columns if c != "スポット"]

    # --- min-max 正規化 ---
    df_norm = spot_scores.copy()
    for col in viewpoint_cols:
        vals = df_norm[col].astype(float)
        if vals.max() == vals.min():
            df_norm[col] = 0.5
        else:
            df_norm[col] = (vals - vals.min()) / (vals.max() - vals.min())

    # --- ユーザ嗜好（観点ランキング） ---
    weights = user_pref_df.set_index("観点")["総合スコア"]

    # --- 条件ごとの観点選択 ---
    if condition == "aspect_top5":
        V = set(weights.sort_values(ascending=False).head(top_k).index)

    elif condition == "aspect_exclude_interest_top5":
        weights_wo_interest = weights.drop(selected_viewpoints, errors="ignore")
        V = set(weights_wo_interest.sort_values(ascending=False).head(top_k).index)

    elif condition == "aspect_all":
        V = set(weights.index)

    elif condition == "noaspect_all":
        # 観点を使わないベースライン
        results = []
        for _, row in df_norm.iterrows():
            spot = row["スポット"]
            score = row[viewpoint_cols].mean()
            results.append({"スポット": spot, "スコア": score})
        return pd.DataFrame(results).sort_values("スコア", ascending=False).head(10)

    else:
        raise ValueError("Unknown condition")

    # --- 観光地スコア計算（方式A） ---
    results = []
    # spot -> {viewpoint: rank}
    spot_viewpoint_rank = {}

    for _, row in df_norm.iterrows():
        spot = row["スポット"]
        ranks = (
            row[viewpoint_cols]
            .sort_values(ascending=False)
            .rank(method="first", ascending=False)
            .astype(int)
        )
        spot_viewpoint_rank[spot] = ranks.to_dict()

        score = 0.0
        for v in V:
            rank = spot_viewpoint_rank[spot][v]
            rank_factor = 1.0 / rank   # ← ここだけ追加

            score += row[v] * weights[v] * rank_factor

        results.append({"スポット": spot, "スコア": score})

    return (
        pd.DataFrame(results)
        .sort_values("スコア", ascending=False)
        .head(10)
    )
