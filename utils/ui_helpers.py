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

def overall_eval_ui(label, dfA):
    st.subheader(f"リスト {label} の全体評価") 
    st.markdown("---")
    st.table(dfA)
    sat = st.slider(f"{label} の推薦結果について、全体としてどの程度満足しましたか？", 1, 5, 3)
    discover = st.slider(f"{label} の推薦結果の中に、知らなかった観光地はどれくらいありましたか？", 1, 5, 3)
    favor = st.slider(f"{label} の推薦結果は、あなたの好みや興味に合っていると感じましたか？", 1, 5, 3)
    st.markdown("---")
    return sat, discover, favor

def show_aspect_eval(label, user_pref_df, selected_viewpoints):
    st.markdown(f"## {label} の観点スコア")

    df = user_pref_df.copy()
    df["スコア"] = df["総合スコア"].round(3)
    df["元々興味あり"] = df["観点"].apply(
        lambda v: "◯" if v in selected_viewpoints else ""
    )
    st.table(df[["観点", "スコア", "元々興味あり"]])

    match = st.slider(f"{label} はあなた自身の認識と一致していると感じましたか？", 1, 5, 3)
    accept = st.slider("表示された観点の中に、意外だと感じたものはありましたか？", 1, 5, 3)
    friendly = st.slider("なぜこれらの観光地が推薦されたのか、理解しやすかったですか？", 1, 5, 3)
    comment = st.text_area(f"{label} に関してよかった点悪かった点があればご記入ください", height=120)

    return match, accept, friendly, comment
