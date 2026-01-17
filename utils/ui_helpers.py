import streamlit as st

def show_title(text):
    st.markdown(f"## {text}")

def info_box(label, content):
    st.info(f"**{label}**\n\n{content}")

def show_ab_tables(dfA, dfB, titleA="リスト A", titleB="リスト B"):
    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"### {titleA}")
        st.table(dfA)
    with colB:
        st.markdown(f"### {titleB}")
        st.table(dfB)

def show_top_viewpoint_scores(spot, spot_scores, top_n=5):
    df = spot_scores.copy()
    cols = [c for c in df.columns if c != "スポット"]

    for col in cols:
        s = df[col].astype(float)
        df[col] = 0.5 if s.max() == s.min() else (s - s.min()) / (s.max() - s.min())

    detail = (
        df[df["スポット"] == spot]
        .drop(columns=["スポット"])
        .T
        .rename(columns={0: "スコア"})
        .sort_values("スコア", ascending=False)
        .head(top_n)
        .round(3)
    )
    st.table(detail)
