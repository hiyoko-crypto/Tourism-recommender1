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

from collections import defaultdict
import pandas as pd
import numpy as np

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
        vals = df[col].astype(float)
        if vals.max() == vals.min():
            df_norm[col] = 0.5
        else:
            df_norm[col] = (vals - vals.min()) / (vals.max() - vals.min())

    # ============================
    # 観点スコア集計（全観点を対象）
    # ============================
    aspect_scores = defaultdict(float)
    boost_rate = 1.2

    for spot in visited_spots:
        row = df_norm[df_norm["スポット"] == spot].iloc[0]
        good_viewpoints = spot_feedback[spot]["viewpoints"]

        for v in viewpoint_cols:
            score = row[v]
            if v in good_viewpoints:
                score *= boost_rate
            aspect_scores[v] += score

    aspect_scores = pd.Series(aspect_scores)
    weights = aspect_scores / aspect_scores.sum()

    # ============================
    # 推薦に使う観点の選択（conditionで分岐）
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
    # UI / ログ用（観点ランキングは常に全観点）
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
    condition
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
