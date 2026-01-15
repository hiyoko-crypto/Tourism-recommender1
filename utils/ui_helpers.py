import streamlit as st

def show_title(text):
    st.markdown(f"## {text}")

def info_box(label, content):
    st.info(f"**{label}**\n\n{content}")

def show_spot_scores(spot_name, spot_scores):
    st.write(f"### {spot_name} の観点スコア")

    row = spot_scores[spot_scores["スポット"] == spot_name]
    if row.empty:
        st.warning("スコアが見つかりませんでした")
        return

    # 「スポット」列を除いた観点スコアを Series に変換
    scores = row.drop(columns=["スポット"]).iloc[0]
    scores_sorted = scores.sort_values(ascending=False)

    # 上位5つのみ抽出
    top5 = scores_sorted.head(5)

    # 表形式で表示
    st.table(top5.reset_index().rename(columns={"index": "観点", 0: "スコア"}))

def get_topk_sequence(condition):
    if condition == "aspect_and_top5":
        return 5
    if condition == "aspect_and_top10":
        return 10
    if condition == "noaspect_and_top5":
        return 5
    if condition == "noaspect_and_top10":
        return 10
    
