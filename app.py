# streamlit run app.py
import streamlit as st
import uuid, random, csv, os
from datetime import datetime

from utils.load_data import load_all, load_viewpoint_descriptions
from utils.scoring import compute_user_preference, recommend_spots

# =====================
# 条件割り当て（最少条件からランダム）
# =====================
CONDITIONS = [
    "aspect_top5",
    "aspect_top10",
    "noaspect_top5",
    "noaspect_top10"
]

def get_condition_from_log():
    if not os.path.exists("experiment_log.csv"):
        return random.choice(CONDITIONS)

    counts = {c: 0 for c in CONDITIONS}

    with open("experiment_log.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cond = row.get("condition")
            if cond in counts:
                counts[cond] += 1

    min_count = min(counts.values())
    candidates = [c for c, v in counts.items() if v == min_count]

    return random.choice(candidates)


# =====================
# 初期化
# =====================
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "condition" not in st.session_state:
    st.session_state.condition = get_condition_from_log()

if "step" not in st.session_state:
    st.session_state.step = 0


# =====================
# ログ保存
# =====================
def save_log(data):
    with open("experiment_log.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if f.tell() == 0:
            writer.writeheader()
        writer.writerow(data)


# =====================
# メイン処理
# =====================
def main():
    st.title("観光地推薦システム（実験）")

    is_aspect = st.session_state.condition.startswith("aspect")

    # =====================
    # Step 0: 説明・同意
    # =====================
    if st.session_state.step == 0:
        st.markdown("""
        ### 実験へのご協力のお願い
        本実験は観光地推薦に関する研究目的で実施されます。
        回答は匿名で収集され、個人が特定されることはありません。
        所要時間は約5〜7分です。
        """)
        name = st.text_input("お名前（ニックネーム可）を入力してください")
        if st.checkbox("内容を理解し、同意します"):
            if st.button("実験を開始する"):
                st.session_state.name = name
                st.session_state.step = 1
                st.rerun()
        return

    viewpoint_list, spot_lists, spot_scores = load_all()
    viewpoint_descriptions = load_viewpoint_descriptions()

    # =====================
    # Step 1: 入力
    # =====================
    if st.session_state.step == 1:

        st.subheader("興味のある観点を選んでください（複数選択可）")

        selected_viewpoints = []

        for i in range(0, len(viewpoint_list), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(viewpoint_list):
                    vp = viewpoint_list[i + j]
                    with col:
                        checked = st.checkbox(vp, key=f"vp_{vp}")
                        if checked:
                            selected_viewpoints.append(vp)

                        desc = viewpoint_descriptions.get(vp, f"{vp} の説明文は準備中です")
                        lines = desc.splitlines()

                        for line in lines[:3]:
                            st.caption(line)

                        if len(lines) > 3:
                            with st.expander("続きを見る"):
                                for line in lines[3:]:
                                    st.write(line)

        st.subheader("行ってよかった観光地を5件選んでください")

        spot_feedback = {}
        visited_spots = []

        for region, spots in spot_lists.items():
            with st.expander(region):
                for i, spot in enumerate(spots):
                    checked = st.checkbox(spot, key=f"spot_{region}_{i}")
                    if checked:
                        visited_spots.append(spot)

                        if is_aspect:
                            viewpoints = st.multiselect(
                                f"{spot} で良かった観点（1つ以上選択してください）",
                                viewpoint_list,
                                key=f"viewpoints_{spot}"
                            )
                        else:
                            viewpoints = []

                        spot_feedback[spot] = {
                            "viewpoints": viewpoints
                        }

        if st.button("次へ"):

            # ★ ちょうど5件チェック ★ 
            if len(visited_spots) != 5:
                st.error(f"観光地をちょうど 5 件選択してください。（現在: {len(visited_spots)} 件）") 
                st.stop() 

            # ★ aspect 条件では観点選択を必須にする 
            if is_aspect: 
                for spot in visited_spots: 
                    if len(spot_feedback[spot]["viewpoints"]) == 0: 
                        st.error(f"{spot} の良かった観点を少なくとも1つ選んでください。") 
                        st.stop()

            st.session_state.selected_viewpoints = selected_viewpoints
            st.session_state.visited_spots = visited_spots
            st.session_state.spot_feedback = spot_feedback

            st.session_state.user_pref = compute_user_preference(
                visited_spots, spot_feedback, spot_scores, selected_viewpoints
            )

            st.session_state.step = 2
            st.rerun()
        return

    # =====================
    # Step 2: 推薦 + 評価
    # =====================
    if st.session_state.step == 2:

        top_k = 5 if "top5" in st.session_state.condition else 10

        st.subheader("観点スコア（ユーザー嗜好）")

        df = st.session_state.user_pref.copy()

        # 小数点3桁に丸める
        df["総合スコア"] = df["総合スコア"].round(3)

        # ★ index を 1,2,3… に変更
        df.index = range(1, len(df) + 1)

        # ★ 興味ありの値を置き換える（1 → 文字列、0 → 空欄）
        df["元々興味あり"] = df["元々興味あり"].apply(
            lambda x: "元々興味あり" if x == 1 else ""
        )

        # ★ 強調スタイル（"元々興味のあった観点" のときだけ太字＋赤）
        def highlight_interest(val):
            if val == "元々興味あり":
                return "font-weight: bold; color: #d9534f;"
            return ""

        styled = (
            df[["観点", "興味あり", "総合スコア"]]
            .style
            .map(highlight_interest, subset=["興味あり"])
            .set_properties(subset=["観点"], **{"font-weight": "bold"})
        )

        st.write(styled)

        rec_df = recommend_spots(
            st.session_state.user_pref,
            spot_scores,
            top_k=top_k
        )

        st.subheader(f"おすすめ観光地（上位 10 件）")

        df_rec = rec_df.copy()
        # ★ index を 1,2,3… に変更
        df_rec.index = range(1, len(df_rec) + 1)

        # 小数点3桁に丸める（必要なら）
        if "スコア" in df_rec.columns:
            df_rec["スコア"] = df_rec["スコア"].round(3)

        # 表示（Styler）
        styled_rec = df_rec.style

        st.write(styled_rec)

        # 上位10件のスポット名をループ
        for idx, row in df_rec.iterrows():
            spot = row["スポット"]
            score = round(row["スコア"], 3)

            # トグル（expander）
            with st.expander(f"{idx}. {spot}（スコア: {score}）"):
                st.write("### 観点スコア")

                # spot_scores から該当スポットの観点スコアを抽出
                spot_detail = spot_scores[spot_scores["スポット"] == spot].copy()

                # 観点スコアだけ取り出す
                detail = spot_detail.drop(columns=["スポット"]).T
                detail.columns = ["スコア"]
                detail["スコア"] = detail["スコア"].round(3)
                detail = detail.sort_values("スコア", ascending=False)

                # 行番号を消す
                detail.index.name = None

                st.table(detail)

        st.markdown("---")
        st.subheader("推薦結果の評価をお願いします")

        sat = st.slider("あなたの好みに合った観光地が推薦されていましたか？", 1, 5, 3)
        nov = st.slider("予想していなかった意外な観光地が含まれていましたか？", 1, 5, 3)
        discover = st.slider("知らなかった魅力的な観光地を新しく知ることができましたか？", 1, 5, 3)

        st.subheader("下のボタンを押すとページが遷移します")
        if st.button("送信"):

            save_log({
                "user_id": st.session_state.user_id,
                "name": st.session_state.name,
                "condition": st.session_state.condition,
                "is_aspect": is_aspect,
                "top_k": top_k,
                "selected_viewpoints": ",".join(st.session_state.selected_viewpoints),
                "visited_spots": ",".join(st.session_state.visited_spots),
                "spot_feedback": str(st.session_state.spot_feedback),
                "satisfaction": sat,
                "novelty": nov,
                "discovery": discover,
                "timestamp": datetime.now().isoformat()
            })

            st.success("ご協力ありがとうございました！")
            st.session_state.step = 3
            st.rerun()
        return

    # =====================
    # Step 3: 完了画面
    # =====================
    if st.session_state.step == 3:
        st.success("実験は以上です。ご協力ありがとうございました！")
        return


if __name__ == "__main__":
    main()
