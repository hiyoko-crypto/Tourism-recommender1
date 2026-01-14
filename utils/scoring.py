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
def compute_user_preference(visited_spots, spot_feedback, df, selected_viewpoints, top_k):
    viewpoint_cols = [c for c in df.columns if c != "スポット"]

    # --- 観点ごとに min-max 正規化 ---
    df_norm = df.copy()
    for col in viewpoint_cols:
        col_values = df[col].astype(float)
        min_v = col_values.min()
        max_v = col_values.max()
        if max_v == min_v:
            df_norm[col] = 0.5
        else:
            df_norm[col] = (col_values - min_v) / (max_v - min_v)

    # --- 訪問スポットの観点スコア合計 ---
    df_visited = df_norm[df_norm["スポット"].isin(visited_spots)]
    base_scores = df_visited[viewpoint_cols].sum()

    # --- 興味あり観点にボーナス ---
    bonus = pd.Series(0, index=viewpoint_cols)
    for vp in selected_viewpoints:
        if vp in bonus.index:
            bonus[vp] += 1.0

    total = base_scores + bonus

    # --- softmax で重み化（全観点） ---
    exp = np.exp(total)
    weights = exp / exp.sum()

    # --- top-k 観点名だけ別途保存 ---
    topk_viewpoints = list(weights.sort_values(ascending=False).head(top_k).index)

    # --- ★ 全観点を返す（ここが重要） ---
    result = pd.DataFrame({
        "観点": weights.index,
        "総合スコア": weights.values,
        "興味あり": [1 if v in selected_viewpoints else 0 for v in weights.index]
    })

    # ★ ここを追加（降順ソート）
    result = result.sort_values("総合スコア", ascending=False).reset_index(drop=True)

    return result, topk_viewpoints


# ============================
# スポット推薦（w^2 × tanh(z)）
# ============================
def recommend_spots(user_pref_df, spot_scores, top_k, topk_viewpoints):

    # --- ユーザー嗜好の順位スコア（全観点） ---
    N = len(user_pref_df)
    user_rank_weight = pd.Series(
        [1 - (i / (N - 1)) for i in range(N)],
        index=user_pref_df["観点"]
    )

    # --- top-k 観点だけ使う ---
    selected_viewpoints = topk_viewpoints

    # --- 観点ごとに min-max 正規化 ---
    df_norm = spot_scores.copy()
    viewpoint_cols = [c for c in df_norm.columns if c != "スポット"]

    for col in viewpoint_cols:
        col_values = df_norm[col].astype(float)
        min_v = col_values.min()
        max_v = col_values.max()
        if max_v == min_v:
            df_norm[col] = 0.5
        else:
            df_norm[col] = (col_values - min_v) / (max_v - min_v)

    results = []
    for _, row in df_norm.iterrows():
        spot = row["スポット"]

        # --- 観光地側の順位スコア ---
        spot_scores_sorted = row[selected_viewpoints].sort_values(ascending=False)
        M = len(spot_scores_sorted)
        spot_rank_weight = pd.Series(
            [1 - (i / (M - 1)) for i in range(M)],
            index=spot_scores_sorted.index
        )

        # --- 最終スコア ---
        score = 0.0
        for vp in selected_viewpoints:
            score += (
                row[vp] *
                user_rank_weight[vp] *
                spot_rank_weight[vp]
            )

        results.append({"スポット": spot, "スコア": score})

    df_rec = pd.DataFrame(results).sort_values("スコア", ascending=False)
    return df_rec.head(10)
