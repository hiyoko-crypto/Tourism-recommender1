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
    # ============================
    # 観点列の抽出
    # ============================
    viewpoint_cols = [c for c in df.columns if c != "スポット"]

    # ============================
    # 観点ごとに min-max 正規化
    # ============================
    df_norm = df.copy()
    for col in viewpoint_cols:
        df_norm[col] = minmax(df_norm[col])

    # ============================
    # 22観点のスコアを初期化
    # ============================
    aspect_scores = {v: 0.0 for v in viewpoint_cols}
    boost_rate = 1.2

    # ============================
    # まず weights を作るために「全観点の素スコア」を計算
    # （topk を決めるために必要）
    # ============================
    tmp_scores = defaultdict(float)

    for spot in visited_spots:
        row = df_norm[df_norm["スポット"] == spot].iloc[0]
        good_viewpoints = spot_feedback[spot]["viewpoints"]
        ranks = row[viewpoint_cols].rank(method="first", ascending=False)

        for v in viewpoint_cols:
            base = row[v]
            rank_factor = 1.0 / ranks[v]
            score = base * rank_factor

            if v in good_viewpoints:
                score *= boost_rate

            tmp_scores[v] += score

    tmp_scores = pd.Series(tmp_scores)

    # ============================
    # topk_viewpoints の決定（condition に応じて）
    # ============================
    if condition == "aspect_top5":
        topk_viewpoints = (
            tmp_scores.sort_values(ascending=False)
            .head(top_k)
            .index
            .tolist()
        )

    elif condition == "aspect_exclude_interest_top5":
        filtered = tmp_scores.drop(selected_viewpoints, errors="ignore")
        topk_viewpoints = (
            filtered.sort_values(ascending=False)
            .head(top_k)
            .index
            .tolist()
        )

    elif condition == "aspect_all":
        topk_viewpoints = list(viewpoint_cols)

    elif condition == "noaspect_all":
        topk_viewpoints = []  # 全観点使うが boost はしない

    else:
        raise ValueError("Unknown condition")

    # ============================
    # ここから本番：visited_spots を回して
    # condition ごとに観点スコアを加算
    # ============================
    for spot in visited_spots:
        row = df_norm[df_norm["スポット"] == spot].iloc[0]
        good_viewpoints = spot_feedback[spot]["viewpoints"]
        ranks = row[viewpoint_cols].rank(method="first", ascending=False)

        # ----------------------------
        # ① aspect_top5
        # ----------------------------
        if condition == "aspect_top5":
            for v in viewpoint_cols:

                # top5 か spot_feedback の観点だけ加算
                if v not in topk_viewpoints and v not in good_viewpoints:
                    continue

                base = row[v]
                rank_factor = 1.0 / ranks[v]
                score = base * rank_factor

                if v in good_viewpoints:
                    score *= boost_rate

                aspect_scores[v] += score

        # ----------------------------
        # ② noaspect_all（全観点・boostなし）
        # ----------------------------
        elif condition == "noaspect_all":
            for v in viewpoint_cols:
                base = row[v]
                rank_factor = 1.0 / ranks[v]
                score = base * rank_factor
                aspect_scores[v] += score

        # ----------------------------
        # ③ aspect_all（全観点・boostあり）
        # ----------------------------
        elif condition == "aspect_all":
            for v in viewpoint_cols:
                base = row[v]
                rank_factor = 1.0 / ranks[v]
                score = base * rank_factor

                if v in good_viewpoints:
                    score *= boost_rate

                aspect_scores[v] += score

        # ----------------------------
        # ④ aspect_exclude_interest_top5
        # ----------------------------
        elif condition == "aspect_exclude_interest_top5":
            for v in viewpoint_cols:

                # selected_viewpoints は除外
                if v in selected_viewpoints:
                    continue

                # top5 か spot_feedback の観点だけ加算
                if v not in topk_viewpoints and v not in good_viewpoints:
                    continue

                base = row[v]
                rank_factor = 1.0 / ranks[v]
                score = base * rank_factor

                if v in good_viewpoints:
                    score *= boost_rate

                aspect_scores[v] += score

    # ============================
    # 最終的な観点スコアを DataFrame に
    # ============================
    aspect_scores = pd.Series(aspect_scores)
    aspect_scores = aspect_scores.sort_values(ascending=False)

    result = pd.DataFrame({
        "観点": aspect_scores.index,
        "総合スコア": aspect_scores.values,
        "興味あり": [1 if v in selected_viewpoints else 0 for v in aspect_scores.index]
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
        V = set(weights.sort_values(ascending=False).head(top_k).index)
    elif condition == "aspect_exclude_interest_top5":
        weights_wo_interest = weights.drop(selected_viewpoints, errors="ignore")
        V = set(weights_wo_interest.sort_values(ascending=False).head(top_k).index)
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
