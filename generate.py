import pandas as pd
import json

# 1. 各種CSVデータの読み込み
# 既存のDataFrameを変数名に割り当てます。
df_live = live_master
df_song = song_master
df_pattern = pattern_detail
df_assign = assign_sheet
df_block = block_master

# 2. 楽曲マスタ・ブロックマスタの辞書化
song_dict = df_song.set_index('楽曲ID')['曲名'].to_dict()

block_dict = {}
for block_id, group in df_block.groupby('ブロックID'):
    block_dict[block_id] = group.sort_values('ブロック内曲順')['楽曲ID'].tolist()

def resolve_code(code, assign_row):
    if pd.isna(code): return None
    code = str(code).strip()
    if code in assign_row and pd.notna(assign_row[code]):
        val = str(assign_row[code]).strip()
        if val in ['M_NAN', 'nan', '']: return None
        return val
    return code

# 3. セトリ内で使用されている楽曲IDの集合（used_song_ids）を作成
used_song_ids = set()

for group in df_block.groupby('ブロックID'):
    for s_id in group[1]['楽曲ID']:
        if pd.notna(s_id):
            used_song_ids.add(str(s_id).strip())

assign_map = df_assign.set_index('公演ID')
live_to_songs = {}

for idx, live in df_live.iterrows():
    live_id = str(live['公演ID'])
    songs_list = []

    if live_id in assign_map.index:
        assign_row = assign_map.loc[live_id]
        if isinstance(assign_row, pd.DataFrame):
            assign_row = assign_row.iloc[0]

        pattern_id = assign_row['パターンID']
        pattern_songs = df_pattern[df_pattern['パターンID'] == pattern_id].sort_values('曲順')['楽曲ID'].tolist()

        song_idx = 1
        for p_code in pattern_songs:
            res1 = resolve_code(p_code, assign_row)
            if not res1: continue

            if res1 in block_dict:
                medley_sub_songs = []
                for b_code in block_dict[res1]:
                    res2 = resolve_code(b_code, assign_row)
                    if res2:
                        used_song_ids.add(res2)
                        medley_sub_songs.append({'id': res2, 'title': song_dict.get(res2, res2)})

                if medley_sub_songs:
                    songs_list.append({
                        'idx': song_idx,
                        'is_medley': True,
                        'title': 'メドレー / コーナー',
                        'medley_songs': medley_sub_songs
                    })
                    song_idx += 1
            else:
                used_song_ids.add(res1)
                songs_list.append({
                    'idx': song_idx,
                    'is_medley': False,
                    'id': res1,
                    'title': song_dict.get(res1, res1)
                })
                song_idx += 1

    live_to_songs[live_id] = songs_list

# 4. ツアーごとに公演データをグループ化
tour_groups = {}
for idx, live in df_live.iterrows():
    live_id = str(live['公演ID'])
    date_str = str(live['日付']) if pd.notna(live['日付']) else ''
    date_num = int(date_str.replace('-', '').replace('/', '')) if date_str and date_str != 'nan' and len(date_str) >= 8 else 0
    venue_str = str(live['都道府県・会場']) if pd.notna(live['都道府県・会場']) else '会場未定'
    tour_str = str(live['ツアー名']) if pd.notna(live['ツアー名']) else '単発・企画公演'
    artist_str = str(live['出演者']) if pd.notna(live['出演者']) else '浦島坂田船'

    live_item = {
        'id': live_id,
        'date': date_str,
        'date_num': date_num,
        'venue': venue_str,
        'tour': tour_str,
        'artist': artist_str,
        'search': f"{date_str} {venue_str} {tour_str} {artist_str}".lower()
    }

    if tour_str not in tour_groups:
        tour_groups[tour_str] = []
    tour_groups[tour_str].append(live_item)

tour_list = []
for tour_name, lives in tour_groups.items():
    lives.sort(key=lambda x: x['date_num'])
    first_date = min(l['date_num'] for l in lives if l['date_num'] > 0) if any(l['date_num'] > 0 for l in lives) else 0
    main_artist = lives[0]['artist'] if lives else '浦島坂田船'

    tour_list.append({
        'tour_name': tour_name,
        'artist': main_artist,
        'first_date': first_date,
        'lives': lives
    })

tour_list.sort(key=lambda x: x['first_date'], reverse=True)

# 5. 楽曲マスタのフィルタリング＆グループ化
artist_song_groups = {}

for idx, song in df_song.iterrows():
    s_id = str(song['楽曲ID']).strip()
    title = str(song['曲名']) if pd.notna(song['曲名']) else ''
    artist = str(song['アーティスト']) if 'アーティスト' in song and pd.notna(song['アーティスト']) else (str(song['区分']) if '区分' in song and pd.notna(song['区分']) else '浦島坂田船')

    is_cover = 'カバー' in artist or ('区分' in song and pd.notna(song['区分']) and 'カバー' in str(song['区分']))
    if is_cover and s_id not in used_song_ids:
        continue

    date_val = ''
    for col in ['投稿日', '投稿日付', 'リリース日', '日付']:
        if col in song and pd.notna(song[col]):
            date_val = str(song[col])
            break

    date_num = int(date_val.replace('-', '').replace('/', '')) if date_val and date_val.replace('-', '').replace('/', '').isdigit() else 0

    item = {
        'id': s_id,
        'title': title,
        'artist': artist,
        'date': date_val,
        'date_num': date_num,
        'search': f"{title} {artist}".lower()
    }

    if artist not in artist_song_groups:
        artist_song_groups[artist] = []
    artist_song_groups[artist].append(item)

artist_song_list = []
for artist_name, songs in artist_song_groups.items():
    artist_song_list.append({
        'artist_name': artist_name,
        'songs': songs
    })

def artist_sort_key(x):
    aname = x['artist_name']
    if '浦島坂田船' in aname: return 0
    if aname in ['うらたぬき', '志麻', 'あほの坂田。', 'となりの坂田。', 'センラ']:
        order_map = {'うらたぬき': 1, '志麻': 2, 'あほの坂田。': 3, 'となりの坂田。': 3, 'センラ': 4}
        return order_map.get(aname, 5)
    return 0.5

artist_song_list.sort(key=artist_sort_key)

# 6. HTML & JavaScript テンプレート
html_template = """<!DOCTYPE html>
<html lang=\"ja\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <meta name="robots" content="noindex,nofollow">
    <title>現場まとめ App</title>
    <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
    <style>
        body { background-color: #f8f9fa; padding-bottom: 60px; font-size: 14px; }
        .nav-tabs .nav-link.active { font-weight: bold; border-bottom: 3px solid #0d6efd; }

        .tour-card, .artist-card { background: white; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid #e9ecef; }

        .tour-header, .artist-header { padding: 10px 15px; font-weight: bold; cursor: pointer; user-select: none; display: flex; justify-content: space-between; align-items: center; transition: opacity 0.2s; color: #212529 !important; }
        .tour-header:hover, .artist-header:hover { opacity: 0.85; }

        .header-usss { background-color: #b3e5fc; } /* 淡い水色 */
        .header-urata { background-color: #c8e6c9; } /* 淡い緑 */
        .header-shima { background-color: #e1bee7; } /* 淡い紫 */
        .header-sakata { background-color: #ffcdd2; } /* 淡い赤 */
        .header-senra { background-color: #fff9c4; } /* 淡い黄色 */
        .header-default { background-color: #e0e0e0; } /* ライトグレー */

        .tour-title, .artist-title { font-size: 0.95em; }

        .live-row, .song-master-row { border-bottom: 1px solid #eee; transition: background 0.2s; }
        .live-row:last-child, .song-master-row:last-child { border-bottom: none; }
        .live-item-header { padding: 10px 15px; cursor: pointer; user-select: none; }
        .live-item-header:hover { background-color: #f8f9fa; }
        .live-title { font-weight: bold; color: #212529; font-size: 0.9em; }

        .setlist-container { background: #fafafa; border-top: 1px solid #eee; padding: 10px 15px; }
        .song-row { padding: 5px 0; border-bottom: 1px dashed #e0e0e0; display: flex; justify-content: space-between; align-items: center; }
        .song-row:last-child { border-bottom: none; }

        .medley-box { background: #f0f0f0; border-left: 3px solid #6c757d; margin: 6px 0; border-radius: 4px; }
        .medley-title { padding: 6px 10px; font-weight: bold; font-size: 0.85em; cursor: pointer; color: #495057; }
        .medley-sub-row { padding: 4px 10px 4px 20px; font-size: 0.82em; color: #555; display: flex; justify-content: space-between; border-top: 1px solid #e9ecef; }

        .play-count { background: #e2e3e5; color: #41464b; border-radius: 10px; padding: 2px 8px; font-size: 0.75em; font-weight: bold; }
        .badge-count { background: #6c757d; color: white; border-radius: 10px; padding: 2px 8px; font-size: 0.75em; }
        .no-song-msg { color: #888; font-style: italic; font-size: 0.85em; text-align: center; padding: 8px; }

        .live-check { width: 18px; height: 18px; cursor: pointer; }
    </style>
</head>
<body>
    <div class=\"container py-3\" style=\"max-width: 800px;\">
        <ul class=\"nav nav-tabs mb-3\">
            <li class=\"nav-item\"><a class=\"nav-link active\" data-bs-toggle=\"tab\" href=\"#tab-lives\">公演一覧 (<span id=\"lives-count-nav\">0</span>)</a></li>
            <li class=\"nav-item\"><a class=\"nav-link\" data-bs-toggle=\"tab\" href=\"#tab-songs\">楽曲一覧 (<span id=\"songs-count-nav\">0</span>)</a></li>
        </ul>

        <div class=\"tab-content\">
            <!-- 公演一覧タブ -->
            <div class=\"tab-pane fade show active\" id=\"tab-lives\">
                <div class=\"row g-2 mb-3\">
                    <div class=\"col\"><input type=\"text\" id=\"search-input\" class=\"form-control\" placeholder=\"ツアー名・会場・日付で検索...\" oninput=\"renderLives()\"></div>
                    <div class=\"col-auto d-flex align-items-center\">
                        <div class=\"form-check form-switch mb-0\">
                            <input class=\"form-check-input\" type=\"checkbox\" id=\"attended-only-switch\" onchange=\"renderLives()\">
                            <label class=\"form-check-label small\" for=\"attended-only-switch\">参戦のみ</label>
                        </div>
                    </div>
                </div>
                <div id=\"lives-list-holder\"></div>
            </div>

            <!-- 楽曲一覧タブ -->
            <div class=\"tab-pane fade\" id=\"tab-songs\">
                <div class=\"row g-2 mb-3\">
                    <div class=\"col\">
                        <input type=\"text\" id=\"song-search\" class=\"form-control\" placeholder=\"曲名で検索...\" oninput=\"renderSongs()\">
                    </div>
                    <div class=\"col-auto\">
                        <select id=\"song-sort-order\" class=\"form-select\" onchange=\"renderSongs()\">
                            <option value=\"asc\">投稿日：古い順</option>
                            <option value=\"desc\">投稿日：新しい順</option>
                        </select>
                    </div>
                </div>
                <div id=\"songs-list-holder\"></div>
            </div>
        </div>
    </div>

    <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js\"></script>
    <script>
    const tourList = %s;
    const liveData = %s;
    const artistSongList = %s;
    const STORAGE_KEY = 'usss_v12_logs';

    let attendedSet = new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]').map(String));
    let globalSongCounts = {};

    function calculateStats() {
        globalSongCounts = {};
        attendedSet.forEach(id => {
            const rawSongs = liveData[id] || liveData[String(id)] || [];
            rawSongs.forEach(item => {
                if (item.is_medley && item.medley_songs) {
                    item.medley_songs.forEach(ms => {
                        const sid = String(ms.id || ms.title);
                        globalSongCounts[sid] = (globalSongCounts[sid] || 0) + 1;
                    });
                } else {
                    const sid = String(item.id || item.title);
                    if (sid) globalSongCounts[sid] = (globalSongCounts[sid] || 0) + 1;
                }
            });
        });
        document.getElementById('lives-count-nav').innerText = attendedSet.size;
        document.getElementById('songs-count-nav').innerText = Object.keys(globalSongCounts).length;
    }

    function getHeaderClass(artist) {
        if (!artist) return 'header-usss';
        const a = String(artist).trim();

        if (a === 'うらたぬき' || a.includes('うらたぬきソロ')) return 'header-urata';
        if (a === '志麻' || a.includes('志麻ソロ')) return 'header-shima';
        if (a === 'あほの坂田。' || a === 'となりの坂田。' || a.includes('坂田ソロ')) return 'header-sakata';
        if (a === 'センラ' || a.includes('センラソロ')) return 'header-senra';

        return 'header-usss';
    }

    function renderSetlistHtml(liveId) {
        const rawSongs = liveData[liveId] || liveData[String(liveId)] || [];
        if (!rawSongs || rawSongs.length === 0) return `<div class=\"no-song-msg\">（セトリ未登録）</div>`;

        let html = '';
        rawSongs.forEach((s, idx) => {
            const songIdx = s.idx || (idx + 1);
            if (s.is_medley) {
                const subSongs = s.medley_songs || [];
                const mId = `medley-${liveId}-${songIdx}`;
                html += `<div class=\"medley-box\">
                    <div class=\"medley-title\" data-bs-toggle=\"collapse\" data-bs-target=\"#${mId}\">
                        🔀 <span class=\"me-1 text-muted\">${songIdx}.</span>${s.title} <small class=\"text-muted\">(${subSongs.length}曲) ▼</small>
                    </div>
                    <div id=\"${mId}\" class=\"collapse\">`;
                subSongs.forEach(ms => {
                    const msId = String(ms.id || ms.title);
                    const cnt = globalSongCounts[msId] || globalSongCounts[ms.title] || 0;
                    const badge = cnt > 0 ? `<span class=\"play-count\">${cnt}回参戦</span>` : '';
                    html += `<div class=\"medley-sub-row\"><span>└ ${ms.title}</span>${badge}</div>`;
                });
                html += `</div></div>`;
            } else {
                const sId = String(s.id || s.title);
                const cnt = globalSongCounts[sId] || globalSongCounts[s.title] || 0;
                const badge = cnt > 0 ? `<span class=\"play-count\">${cnt}回参戦</span>` : '';
                html += `<div class=\"song-row\">
                    <span><span class=\"me-2 text-muted fw-bold\">${songIdx}.</span>${s.title}</span>
                    ${badge}
                </div>`;
            }
        });
        return html;
    }

    function renderLives() {
        const holder = document.getElementById('lives-list-holder');
        if (!holder) return;

        const kw = (document.getElementById('search-input') || {value:""}).value.toLowerCase();
        const attendedOnly = (document.getElementById('attended-only-switch') || {checked:false}).checked;

        let htmlBuffer = '';

        tourList.forEach((tourGroup, tIdx) => {
            let tourLivesHtml = '';
            let visibleLiveCount = 0;
            let tourAttendedCount = 0;

            tourGroup.lives.forEach(live => {
                const liveIdStr = String(live.id);
                const isAttended = attendedSet.has(liveIdStr);
                if (isAttended) tourAttendedCount++;

                if (attendedOnly && !isAttended) return;
                if (kw !== "" && !live.search.includes(kw)) return;

                visibleLiveCount++;
                const checked = isAttended ? 'checked' : '';
                const songs = liveData[liveIdStr] || [];
                const songBadge = songs.length > 0 ? `<span class=\"badge-count me-2\">${songs.length}曲</span>` : '';

                tourLivesHtml += `
                <div class=\"live-row\">
                    <div class=\"live-item-header d-flex align-items-center\">
                        <div class=\"pe-2\" onclick=\"event.stopPropagation();\">
                            <input type=\"checkbox\" class=\"live-check\" data-live-id=\"${liveIdStr}\" ${checked} onchange=\"handleCheckChange(this)\">
                        </div>
                        <div class=\"flex-grow-1\" data-bs-toggle=\"collapse\" data-bs-target=\"#setlist-${liveIdStr}\">
                            <div class=\"live-title\">📅 ${live.date} | 📍 ${live.venue}</div>
                        </div>
                        <div data-bs-toggle=\"collapse\" data-bs-target=\"#setlist-${liveIdStr}\">
                            ${songBadge}
                            <small class=\"text-muted\">▼</small>
                        </div>
                    </div>
                    <div id=\"setlist-${liveIdStr}\" class=\"collapse\">
                        <div class=\"setlist-container\">
                            ${renderSetlistHtml(liveIdStr)}
                        </div>
                    </div>
                </div>`;
            });

            if (visibleLiveCount > 0) {
                const tourCollapseId = `tour-group-${tIdx}`;
                const isOpen = kw !== "" || attendedOnly;
                const collapseClass = isOpen ? 'show' : '';

                const tourBadge = tourAttendedCount > 0 ? `<span class=\"badge bg-white text-dark border ms-2\">${tourAttendedCount}/${tourGroup.lives.length}参戦</span>` : `<span class=\"badge bg-white text-dark border opacity-75 ms-2\">${tourGroup.lives.length}公演</span>`;
                const headerClass = getHeaderClass(tourGroup.artist);

                htmlBuffer += `
                <div class=\"tour-card\">
                    <div class=\"tour-header ${headerClass}\" data-bs-toggle=\"collapse\" data-bs-target=\"#${tourCollapseId}\">
                        <div class=\"tour-title\">${tourGroup.tour_name} ${tourBadge}</div>
                        <div><small>▼</small></div>
                    </div>
                    <div id=\"${tourCollapseId}\" class=\"collapse ${collapseClass}\">
                        <div>${tourLivesHtml}</div>
                    </div>
                </div>`;
            }
        });

        if (htmlBuffer === '') {
            htmlBuffer = '<div class=\"text-center text-muted py-4\">条件に一致する公演が見つかりませんでした。</div>';
        }

        holder.innerHTML = htmlBuffer;
    }

    function renderSongs() {
        const holder = document.getElementById('songs-list-holder');
        if(!holder) return;

        const kw = (document.getElementById('song-search') || {value:""}).value.toLowerCase();
        const sortOrder = (document.getElementById('song-sort-order') || {value:"asc"}).value;

        let htmlBuffer = '';

        artistSongList.forEach((aGroup, aIdx) => {
            // ソート処理（昇順/降順）
            const sortedSongs = [...aGroup.songs].sort((a, b) => {
                return sortOrder === 'asc' ? a.date_num - b.date_num : b.date_num - a.date_num;
            });

            let songsHtml = '';
            let visibleSongCount = 0;

            sortedSongs.forEach(s => {
                if (kw !== "" && !s.search.includes(kw)) return;

                visibleSongCount++;
                const sId = String(s.id || s.title);
                const cnt = globalSongCounts[sId] || globalSongCounts[s.title] || 0;
                const badge = cnt > 0 ? `<span class=\"play-count\">${cnt}回参戦</span>` : '<span class=\"text-muted small\">未参戦</span>';
                const dateDisplay = s.date ? `<small class=\"text-muted me-2\">${s.date}</small>` : '';

                songsHtml += `
                <div class=\"song-master-row p-2.5 px-3 border-bottom d-flex justify-content-between align-items-center\">
                    <div>
                        <div class=\"fw-bold\" style=\"font-size: 0.9em;\">${s.title}</div>
                        <div>${dateDisplay}</div>
                    </div>
                    <div>${badge}</div>
                </div>`;
            });

            if (visibleSongCount > 0) {
                const artistCollapseId = `artist-group-${aIdx}`;
                const isOpen = kw !== "";
                const collapseClass = isOpen ? 'show' : '';
                const headerClass = getHeaderClass(aGroup.artist_name);

                htmlBuffer += `
                <div class=\"artist-card\">
                    <div class=\"artist-header ${headerClass}\" data-bs-toggle=\"collapse\" data-bs-target=\"#${artistCollapseId}\">
                        <div class=\"artist-title\">${aGroup.artist_name} <span class=\"badge bg-white text-dark border ms-2\">${aGroup.songs.length}曲</span></div>
                        <div><small>▼</small></div>
                    </div>
                    <div id=\"${artistCollapseId}\" class=\"collapse ${collapseClass}\">
                        <div>${songsHtml}</div>
                    </div>
                </div>`;
            }
        });

        if (htmlBuffer === '') {
            htmlBuffer = '<div class=\"text-center text-muted py-4\">条件に一致する楽曲が見つかりませんでした。</div>';
        }

        holder.innerHTML = htmlBuffer;
    }

    function handleCheckChange(checkbox) {
        const liveId = String(checkbox.dataset.liveId);
        if(checkbox.checked) { attendedSet.add(liveId); } else { attendedSet.delete(liveId); }
        localStorage.setItem(STORAGE_KEY, JSON.stringify([...attendedSet]));
        calculateStats();
        renderLives();
        renderSongs();
    }

    window.onload = () => {
        calculateStats();
        renderLives();
        renderSongs();
    };
    </script>
</body>
</html>
""" % (
    json.dumps(tour_list, ensure_ascii=False),
    json.dumps(live_to_songs, ensure_ascii=False),
    json.dumps(artist_song_list, ensure_ascii=False)
)

# 7. ファイル出力
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print("✅ 'index.html' の生成が完了しました！")