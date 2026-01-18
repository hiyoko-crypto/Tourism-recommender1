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

def compute_user_preference(
    visited_spots,
    spot_feedback,
    df,
    selected_viewpoints,
    condition
):
    # ============================
    # 観点列
    # ============================
    viewpoint_cols = [c for c in df.columns if c != "スポット"]

    # ============================
    # min-max 正規化
    # ============================
    df_norm = df.copy()
    for col in viewpoint_cols:
        df_norm[col] = minmax(df_norm[col])

    # ============================
    # 観点スコア初期化
    # ============================
    aspect_scores = defaultdict(float)
    boost_rate = 1.2

    # ============================
    # 各 visited_spot を独立に処理
    # ============================
    for spot in visited_spots:
        row = df_norm[df_norm["スポット"] == spot].iloc[0]
        good_viewpoints = spot_feedback.get(spot, {}).get("viewpoints", [])

        # 観光地内順位（1位が1）
        ranks = row[viewpoint_cols].rank(ascending=False, method="first")

        # --- spot-local top5 ---
        if condition == "aspect_top5":
            spot_top = set(
                ranks.sort_values().head(5).index
            )

        elif condition == "aspect_exclude_interest_top5":
            filtered = ranks.drop(selected_viewpoints, errors="ignore")
            spot_top = set(
                filtered.sort_values().head(5).index
            )

        else:
            spot_top = None  # noaspect_all / aspect_all

        # ============================
        # 観点ごとの加算判定
        # ============================
        for v in viewpoint_cols:
            use_flag = False

            if condition == "noaspect_all":
                use_flag = True

            elif condition == "aspect_all":
                use_flag = True

            elif condition in ["aspect_top5", "aspect_exclude_interest_top5"]:
                if v in spot_top or v in good_viewpoints:
                    use_flag = True

            if not use_flag:
                continue

            # --- スコア計算 ---
            base = row[v]
            rank_factor = 1.0 / ranks[v]
            score = base * rank_factor

            if condition != "noaspect_all" and v in good_viewpoints:
                score *= boost_rate

            aspect_scores[v] += score

    # ============================
    # 結果整形
    # ============================
    aspect_scores = pd.Series(aspect_scores).sort_values(ascending=False)

    result = pd.DataFrame({
        "観点": aspect_scores.index,
        "総合スコア": aspect_scores.values,
        "興味あり": [1 if v in selected_viewpoints else 0 for v in aspect_scores.index]
    }).reset_index(drop=True)

    return result

# ============================
# スポット推薦
# ============================
def recommend_spots(
    user_pref_df,
    spot_scores,
    condition,
    selected_viewpoints,
    visited_spots=None
):
    if visited_spots is None:
        visited_spots = []

    viewpoint_cols = [c for c in spot_scores.columns if c != "スポット"]

    # --- min-max 正規化 ---
    df_norm = spot_scores.copy()
    for col in viewpoint_cols:
        df_norm[col] = minmax(df_norm[col])

    # ============================ 
    # ② 観点順位の逆数（1/rank）を計算 
    # ============================ 
    rank_df = df_norm.copy() 
    for idx, row in df_norm.iterrows():
        ranks = row[viewpoint_cols].rank(method="first", ascending=False)
        rank_df.loc[idx, viewpoint_cols] = 1.0 / ranks
    
    # --- ユーザ嗜好重み ---
    weights = user_pref_df.set_index("観点")["総合スコア"]

    # --- 観点集合 ---
    if condition == "aspect_top5":
        V = set(weights.sort_values(ascending=False).head(5).index)
    elif condition == "aspect_exclude_interest_top5":
        weights_wo_interest = weights.drop(selected_viewpoints, errors="ignore")
        V = set(weights_wo_interest.sort_values(ascending=False).head(5).index)
    elif condition == "aspect_all":
        V = set(weights.index)
    elif condition == "noaspect_all":
        results = []
        for idx, row in df_norm.iterrows():
            spot = row["スポット"]
            score = 0.0
            for v in viewpoint_cols:
                base = row[v]
                rank_factor = rank_df.loc[idx, v]
                score += base * rank_factor
            results.append({"スポット": spot, "スコア": score})
    
        df_all = pd.DataFrame(results).sort_values("スコア", ascending=False)
    else:
        raise ValueError("Unknown condition")

    # --- スコア計算（元コードそのまま） ---
    if condition != "noaspect_all":
        results = []
        for idx, row in df_norm.iterrows():
            spot = row["スポット"]
            score = 0.0
            for v in V:
                base = row[v]
                rank_factor = rank_df.loc[idx, v]
                weight = weights[v]
                
                score += weight * base * rank_factor
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
