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
import pandas as pd
import numpy as np
from collections import defaultdict

def compute_user_preference(
    visited_spots,
    spot_feedback,
    df,
    selected_viewpoints,
    top_k,
    condition
):
    viewpoint_cols = [c for c in df.columns if c != "スポット"]

    # ============================
    # 観点ごとに min-max 正規化
    # ============================
    df_norm = df.copy()
    for col in viewpoint_cols:
        df_norm[col] = minmax(df_norm[col])

    # ============================
    # ユーザ嗜好観点スコア算出
    # ============================
    aspect_scores = defaultdict(float)
    boost_rate = 1.2

    for spot in visited_spots:
        row = df_norm[df_norm["スポット"] == spot].iloc[0]
        good_viewpoints = spot_feedback[spot]["viewpoints"]

        # 観光地内での観点順位
        ranks = (
            row[viewpoint_cols]
            .sort_values(ascending=False)
            .rank(method="first", ascending=False)
        )

        for v in viewpoint_cols:
            base_score = row[v]
            rank_factor = 1.0 / ranks[v]

            score = base_score * rank_factor

            if v in good_viewpoints:
                score *= boost_rate

            aspect_scores[v] += score

    aspect_scores = pd.Series(aspect_scores)

    # 正規化（総和 = 1）
    if aspect_scores.sum() == 0:
        weights = aspect_scores.copy()
    else:
        weights = aspect_scores / aspect_scores.sum()

    # ============================
    # 推薦に使う観点集合（条件分岐）
    # ============================
    if condition == "aspect_top5":
        topk_viewpoints = (
            weights.sort_values(ascending=False)
            .head(top_k)
            .index
            .tolist()
        )

    elif condition == "aspect_exclude_interest_top5":
        filtered = weights.drop(selected_viewpoints, errors="ignore")
        topk_viewpoints = (
            filtered.sort_values(ascending=False)
            .head(top_k)
            .index
            .tolist()
        )

    elif condition == "aspect_all":
        topk_viewpoints = list(weights.index)

    elif condition == "noaspect_all":
        topk_viewpoints = []

    else:
        raise ValueError("Unknown condition")

    # ============================
    # UI / ログ用（全観点ランキング）
    # ============================
    weights_for_ui = weights.sort_values(ascending=False)

    result = pd.DataFrame({
        "観点": weights_for_ui.index,
        "総合スコア": weights_for_ui.values,
        "興味あり": [1 if v in selected_viewpoints else 0 for v in weights_for_ui.index]
    }).reset_index(drop=True)

    return result, topk_viewpoints


# ============================
# スポット推薦
# ============================
def recommend_spots(
    user_pref_df,
    spot_scores,
    condition,
    selected_viewpoints,
    top_k=5,
    visited_spots=None
):
    if visited_spots is None:
        visited_spots = []

    viewpoint_cols = [c for c in spot_scores.columns if c != "スポット"]

    # --- min-max 正規化 ---
    df_norm = spot_scores.copy()
    for col in viewpoint_cols:
        df_norm[col] = minmax(df_norm[col])

    # --- ユーザ嗜好重み ---
    weights = user_pref_df.set_index("観点")["総合スコア"]

    # --- 観点集合 ---
    if condition == "aspect_top5":
        V = set(weights.sort_values(ascending=False).head(top_k).index)
    elif condition == "aspect_exclude_interest_top5":
        weights_wo_interest = weights.drop(selected_viewpoints, errors="ignore")
        V = set(weights_wo_interest.sort_values(ascending=False).head(top_k).index)
    elif condition == "aspect_all":
        V = set(weights.index)
    elif condition == "noaspect_all":
        results = []
        for _, row in df_norm.iterrows():
            spot = row["スポット"]
            score = row[viewpoint_cols].mean()
            results.append({"スポット": spot, "スコア": score})
        df_all = pd.DataFrame(results).sort_values("スコア", ascending=False)
    else:
        raise ValueError("Unknown condition")

    # --- スコア計算（元コードそのまま） ---
    if condition != "noaspect_all":
        results = []
        for _, row in df_norm.iterrows():
            spot = row["スポット"]
            score = 0.0
            for v in V:
                score += weights[v] * row[v]
            results.append({"スポット": spot, "スコア": score})

        df_all = pd.DataFrame(results).sort_values("スコア", ascending=False)

    # ============================
    # ★ 除外スポットの記録（追加）
    # ============================
    excluded = []
    for rank, (_, row) in enumerate(df_all.iterrows(), start=1):
        if row["スポット"] in visited_spots:
            excluded.append({"スポット": row["スポット"], "順位": rank})

    # ============================
    # ★ visited_spots を除外（追加）
    # ============================
    df_filtered = df_all[~df_all["スポット"].isin(visited_spots)]

    # --- 上位10件を返す ---
    df_rec = df_filtered.head(10)

    return df_rec, excluded
