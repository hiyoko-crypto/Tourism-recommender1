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

def overall_eval_ui(label):
    st.subheader(f"{label} の全体評価")
    sat = st.slider(f"{label} の推薦結果の満足度", 1, 5, 3)
    discover = st.slider(f"{label} に新規性はありましたか？", 1, 5, 3)
    favor = st.slider(f"{label} は好みに合っていましたか？", 1, 5, 3)
    return sat, discover, favor
