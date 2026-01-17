import streamlit as st
import json
import uuid, random, csv, os
from datetime import datetime

from utils.load_data import load_all, load_viewpoint_descriptions, load_spot_urls
from utils.scoring import compute_user_preference, recommend_spots
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# =====================
# 条件割り当て（最少条件からランダム）
# =====================
CONDITIONS = [
    "noaspect_all",
    "aspect_all",
    "aspect_top5",
    "aspect_exclude_interest_top5"
]


def get_condition_from_log():
    # Google Sheets 認証
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)

    # スプレッドシートを開く
    sheet = client.open_by_key(
        st.secrets["gcp_service_account"]["sheet_id"]
    ).sheet1

    # 全データ取得
    values = sheet.get_all_values()

    # ログがまだ無い場合
    if len(values) <= 1:
        return random.choice(CONDITIONS)
    header = values[0] # 1行目 
    data_rows = values[1:] # 2行目以降 
    
    # "condition" 列のインデックスを探す 
    try: 
        cond_idx = header.index("condition") 
    except ValueError: 
        # ヘッダーに "condition" が無い場合はランダム 
        return random.choice(CONDITIONS)
    
    
    # 条件のカウント
    counts = {c: 0 for c in CONDITIONS}

    for row in data_rows: 
        if len(row) <= cond_idx: 
            continue 
        cond = row[cond_idx] 
        if cond in counts: 
            counts[cond] += 1 
    
    # ログが実質ない場合 
    if all(v == 0 for v in counts.values()): 
        return random.choice(CONDITIONS) 
        
    # 最小値の条件を選ぶ 
    min_count = min(counts.values()) 
    candidates = [c for c, v in counts.items() if v == min_count] 

    return random.choice(candidates)

# =====================
# 初期化
# =====================
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "step" not in st.session_state:
    st.session_state.step = 0


# =====================
# ログ保存
# =====================
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def save_log(data):
    # Google Sheets 認証
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)

    sheet = client.open_by_key(
        st.secrets["gcp_service_account"]["sheet_id"]
    ).sheet1

    # 既存データを取得
    existing = sheet.get_all_values()

    # ============================
    # ★ ログがまだ無い場合（1行目が空）
    # ============================
    if len(existing) == 0:
        header = list(data.keys())  # ← data のキーをそのままヘッダーにする
        sheet.append_row(header)

    else:
        # 既存ヘッダーを取得
        header = existing[0]

        # ★ data に新しいキーが追加されていたらヘッダーに追加する
        new_keys = [k for k in data.keys() if k not in header]
        if new_keys:
            header += new_keys
            sheet.update('1:1', [header])  # 1行目を更新

    # ============================
    # ★ ヘッダー順にデータを並べる
    # ============================
    row = [data.get(col, "") for col in header]

    sheet.append_row(row)


# =====================
# メイン処理
# =====================
def main():
    st.title("観光地推薦システム（実験）")

    is_aspect = False
    if "condition" in st.session_state:
        is_aspect = st.session_state.condition.startswith("aspect")
    spot_url_dict = load_spot_urls()

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
        st.subheader("参加者情報の入力")
        name = st.text_input("お名前（ニックネーム可）を入力してください")
        age_group = st.selectbox( "年代を選択してください", ["10代", "20代", "30代", "40代", "50代", "60代以上"] )
        if st.checkbox("内容を理解し、同意します"):
            if st.button("実験を開始する"):
                st.session_state.name = name
                st.session_state.age_group = age_group
                st.session_state.condition = get_condition_from_log()
                st.session_state.step = 1
                st.rerun()
        return

    viewpoint_list, spot_lists, spot_scores = load_all()
    viewpoint_descriptions = load_viewpoint_descriptions()

    # =====================
    # Step 1: 興味のある観点 + 行った観光地
    # =====================
    if st.session_state.step == 1:

        st.subheader("興味のある観点を選んでください（1つ以上選択）")

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
                    checked = st.checkbox(spot, key=f"spot_{region}_{spot}")
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

        # 右上に選択数を表示
        col_left, col_right = st.columns([1, 1])
        with col_right:
            st.markdown(
                f"<div style='text-align: right; font-size: 18px; font-weight: bold;'>"
                f"現在の選択数：{len(visited_spots)} 件"
                f"</div>",
                unsafe_allow_html=True
            )

        if st.button("次へ"):

            if len(visited_spots) != 5:
                st.error(f"観光地をちょうど 5 件選択してください。（現在: {len(visited_spots)} 件）") 
                st.stop() 

            if is_aspect: 
                for spot in visited_spots: 
                    if len(spot_feedback[spot]["viewpoints"]) == 0: 
                        st.error(f"{spot} の良かった観点を少なくとも1つ選んでください。") 
                        st.stop()

            st.session_state.selected_viewpoints = selected_viewpoints
            st.session_state.visited_spots = visited_spots
            st.session_state.spot_feedback = spot_feedback

            top_k = 5 if "top5" in st.session_state.condition else 10

            st.session_state.user_pref, st.session_state.topk_viewpoints = compute_user_preference(
                visited_spots,
                spot_feedback,
                spot_scores,
                selected_viewpoints,
                top_k,
                st.session_state.condition
            )

            st.session_state.step = 2
            st.rerun()
        return

    # =====================
    # Step 2: 推薦 + アンケート（観点スコアはまだ見せない）
    # =====================
    if st.session_state.step == 2:

        top_k = 5 if "top5" in st.session_state.condition else 10

        st.subheader("おすすめ観光地（上位 10 件）")

        rec_df, excluded_spots = recommend_spots(
            user_pref_df=st.session_state.user_pref,
            spot_scores=spot_scores,
            condition=st.session_state.condition,
            selected_viewpoints=st.session_state.selected_viewpoints,
            top_k=top_k,
            visited_spots=st.session_state.visited_spots
        )

        st.session_state.excluded_spots = excluded_spots
        df_rec = rec_df.copy()
        df_rec.index = range(1, len(df_rec) + 1)

        if "スコア" in df_rec.columns:
            df_rec["スコア"] = df_rec["スコア"].round(3)

        st.write(df_rec)        

        st.markdown("---")
        st.subheader("推薦結果の評価をお願いします")

        st.subheader("各観光地ごとに評価をお願いします")

        # --- 観点ごとに min-max 正規化（ループ前に実行） ---
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

        # --- 推薦結果の表示 ---
        for idx, row in df_rec.iterrows():
            spot = row["スポット"]
            score = round(row["スコア"], 3)

            # ▼ トグル（観点スコアだけ表示）
            with st.expander(f"{idx}. {spot}（スコア: {score}）"):
                st.write("#### 観点スコア")

                detail = (
                    df_norm[df_norm["スポット"] == spot]
                    .drop(columns=["スポット"])
                    .T
                )
                detail.columns = ["スコア"]
                detail["スコア"] = detail["スコア"].round(3)
                detail = detail.sort_values("スコア", ascending=False).head(5)

                st.table(detail)

                # ▼ 口コミURLを表示
                if spot in spot_url_dict:
                    st.markdown(f"**口コミURL：** [こちらをクリック]({spot_url_dict[spot]})")
                else:
                    st.caption("口コミURLは登録されていません")

            # ▼ トグルの外に質問を置く（ここがポイント）
            visited = st.radio(
                "この観光地に行ったことはありますか？",
                ["行ったことがない" , "行ったことがある"],
                key=f"visited_{spot}"
            )
            st.caption("※ 行ったことがある場合は「また行きたいか」、ない場合は「行ってみたいか」で評価してください")
            
            likability = st.slider(
                f"{spot} に行ってみたいと思いましたか？",
                1, 5, 3,
                key=f"like_{spot}"
            )

            # 保存用
            if "spot_questions" not in st.session_state:
                st.session_state.spot_questions = {}

            st.session_state.spot_questions[spot] = {
                "likability": likability,
                "visited": visited
            }


        # 推薦全体に対する評価
        st.subheader("ここからは推薦全体に対して評価していただきます")
        sat = st.slider("提示された観光地の推薦結果について、全体としてどの程度満足しましたか？", 1, 5, 3)
        discover = st.slider("推薦結果の中に、これまで知らなかった・考えたことのなかった観光地はありましたか？", 1, 5, 3)        
        favor = st.slider(
            "今回の推薦結果は、あなたの好みや興味に合っていると感じましたか？",
            1, 5, 3
        )
        st.markdown("---")

        spot_comment = st.text_area(
            "今回の推薦結果について、良いと感じた点や違和感を覚えた点があれば自由にお書きください。",
            height=150 
        )

        if st.button("次へ"):
            st.session_state.sat = sat
            st.session_state.discover = discover
            st.session_state.likability = likability
            st.session_state.spot_comment = spot_comment
            st.session_state.favor = favor
            st.session_state.step = 3
            st.rerun()
        return

    # =====================
    # Step 3: 観点スコア（種明かし） + アンケート
    # =====================
    if st.session_state.step == 3:

        st.subheader("あなたの好みの観点（推定結果）")

        df = st.session_state.user_pref.copy()
        df["スコア"] = df["総合スコア"].round(3)
        df.index = range(1, len(df) + 1)

        df["元々興味あり"] = df["観点"].apply(
            lambda v: "◯" if v in st.session_state.selected_viewpoints else ""
        )

        st.table(df[["観点", "スコア", "元々興味あり"]])

        st.markdown("---")

        match = st.slider(
            "この「あなたの好みの観点」は、あなた自身の認識と一致していると感じましたか？",
            1, 5, 3
        )
        accept = st.slider(
            "表示された観点の中に、意外だと感じたものはありましたか？",
            1, 5, 3
        )
        friendly = st.slider(
            "なぜこれらの観光地が推薦されたのか、理解しやすかったですか？",
            1, 5, 3
        )
        aspect_comment = st.text_area(
            "今回の「あなたの好みの観点」について、良いと感じた点や違和感を覚えた点があれば自由にお書きください。",
            height=150 
        )        


        if st.button("送信して終了"):
            save_log({
                "user_id": st.session_state.user_id,
                "name": st.session_state.name,
                "age_group": st.session_state.age_group,
                "condition": st.session_state.condition,
                "selected_viewpoints": ",".join(st.session_state.selected_viewpoints),
                "visited_spots": ",".join(st.session_state.visited_spots),
                "spot_feedback": json.dumps(st.session_state.spot_feedback, ensure_ascii=False),
                "spot_questions": json.dumps(st.session_state.spot_questions, ensure_ascii=False),
                "satisfaction": st.session_state.sat,
                "discovery": st.session_state.discover,
                "favor": st.session_state.favor,
                "spot_comment": st.session_state.spot_comment,
                "user_pref_ranking": json.dumps(
                    st.session_state.user_pref.to_dict(orient="records"),
                    ensure_ascii=False
                ),
                "excluded_spots": json.dumps(st.session_state.excluded_spots, ensure_ascii=False),
                "match": match,
                "accept": accept,
                "friendly": friendly,
                "aspect_comment": aspect_comment,
                "timestamp": datetime.now().isoformat()
            })

            st.success("ご協力ありがとうございました！")
            st.session_state.step = 4
            st.rerun()
        return

    # =====================
    # Step 4: 完了画面
    # =====================
    if st.session_state.step == 4:
        st.success("実験は以上です。ご協力ありがとうございました！")
        return


if __name__ == "__main__":
    main()
