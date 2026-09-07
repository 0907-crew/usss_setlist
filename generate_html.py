import json
import pandas as pd

# CSVファイルの読み込み
df_live = pd.read_csv('浦島坂田船 現場まとめ - 公演マスタ.csv', encoding='utf-8')
df_song = pd.read_csv('浦島坂田船 現場まとめ - 楽曲マスタ.csv', encoding='utf-8')
df_pattern = pd.read_csv(
    '浦島坂田船 現場まとめ - セトリパターン詳細.csv', encoding='utf-8'
)
df_assign = pd.read_csv(
    '浦島坂田船 現場まとめ - セトリ割当シート.csv', encoding='utf-8'
)
df_block = pd.read_csv(
    '浦島坂田船 現場まとめ - ブロックマスタ.csv', encoding='utf-8'
)

# 2. 楽曲マスタ・ブロックマスタの辞書化
song_dict = df_song.set_index('楽曲ID')['曲名'].to_dict()

block_dict = {}
for block_id, group in df_block.groupby('ブロックID'):
  block_dict[block_id] = (
      group.sort_values('ブロック内曲順')['楽曲ID'].tolist()
  )


def resolve_code(code, assign_row):
  if pd.isna(code):
    return None
  code = str(code).strip()
  if code in assign_row and pd.notna(assign_row[code]):
    val = str(assign_row[code]).strip()
    if val in ['M_NAN', 'nan', '']:
      return None
    return val
  return code


# 3. セトリ内で使用されている楽曲IDの集合を作成
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
    pattern_songs = (
        df_pattern[df_pattern['パターンID'] == pattern_id]
        .sort_values('曲順')['楽曲ID']
        .tolist()
    )

    song_idx = 1
    for p_code in pattern_songs:
      res1 = resolve_code(p_code, assign_row)
      if not res1:
        continue

      if res1 in block_dict:
        medley_sub_songs = []
        for b_code in block_dict[res1]:
          res2 = resolve_code(b_code, assign_row)
          if res2:
            used_song_ids.add(res2)
            medley_sub_songs.append(
                {'id': res2, 'title': song_dict.get(res2, res2)}
            )

        if medley_sub_songs:
          songs_list.append({
              'idx': song_idx,
              'is_medley': True,
              'title': 'メドレー / コーナー',
              'medley_songs': medley_sub_songs,
          })
          song_idx += 1
      else:
        used_song_ids.add(res1)
        songs_list.append({
            'idx': song_idx,
            'is_medley': False,
            'id': res1,
            'title': song_dict.get(res1, res1),
        })
        song_idx += 1

  live_to_songs[live_id] = songs_list

# 4. ツアーごとに公演データをグループ化
tour_groups = {}
for idx, live in df_live.iterrows():
  live_id = str(live['公演ID'])
  date_str = str(live['日付']) if pd.notna(live['日付']) else ''
  date_num = (
      int(date_str.replace('-', '').replace('/', ''))
      if date_str and date_str != 'nan' and len(date_str) >= 8
      else 0
  )
  venue_str = (
      str(live['都道府県・会場'])
      if pd.notna(live['都道府県・会場'])
      else '会場未定'
  )
  tour_str = (
      str(live['ツアー名']) if pd.notna(live['ツアー名']) else '単発・企画公演'
  )
  artist_str = (
      str(live['出演者']) if pd.notna(live['出演者']) else '浦島坂田船'
  )

  live_item = {
      'id': live_id,
      'date': date_str,
      'date_num': date_num,
      'venue': venue_str,
      'tour': tour_str,
      'artist': artist_str,
      'search': f'{date_str} {venue_str} {tour_str} {artist_str}'.lower(),
  }

  if tour_str not in tour_groups:
    tour_groups[tour_str] = []
  tour_groups[tour_str].append(live_item)

tour_list = []
for tour_name, lives in tour_groups.items():
  lives.sort(key=lambda x: x['date_num'])
  first_date = (
      min(l['date_num'] for l in lives if l['date_num'] > 0)
      if any(l['date_num'] > 0 for l in lives)
      else 0
  )
  main_artist = lives[0]['artist'] if lives else '浦島坂田船'

  tour_list.append({
      'tour_name': tour_name,
      'artist': main_artist,
      'first_date': first_date,
      'lives': lives,
  })

tour_list.sort(key=lambda x: x['first_date'], reverse=True)

# 5. 楽曲マスタのフィルタリング＆グループ化
artist_song_groups = {}
for idx, song in df_song.iterrows():
  s_id = str(song['楽曲ID']).strip()
  title = str(song['曲名']) if pd.notna(song['曲名']) else ''
  artist = (
      str(song['アーティスト'])
      if 'アーティスト' in song and pd.notna(song['アーティスト'])
      else (
          str(song['区分'])
          if '区分' in song and pd.notna(song['区分'])
          else '浦島坂田船'
      )
  )

  is_cover = 'カバー' in artist or (
      '区分' in song and pd.notna(song['区分']) and 'カバー' in str(song['区分'])
  )
  if is_cover and s_id not in used_song_ids:
    continue

  date_val = ''
  for col in ['投稿日', '投稿日付', 'リリース日', '日付']:
    if col in song and pd.notna(song[col]):
      date_val = str(song[col])
      break

  date_num = (
      int(date_val.replace('-', '').replace('/', ''))
      if date_val and date_val.replace('-', '').replace('/', '').isdigit()
      else 0
  )

  item = {
      'id': s_id,
      'title': title,
      'artist': artist,
      'date': date_val,
      'date_num': date_num,
      'search': f'{title} {artist}'.lower(),
  }

  if artist not in artist_song_groups:
    artist_song_groups[artist] = []
  artist_song_groups[artist].append(item)

artist_song_list = []
for artist_name, songs in artist_song_groups.items():
  artist_song_list.append({'artist_name': artist_name, 'songs': songs})


def artist_sort_key(x):
  aname = x['artist_name']
  if '浦島坂田船' in aname:
    return 0
  if aname in ['うらたぬき', '志麻', 'あほの坂田。', 'となりの坂田。', 'センラ']:
    order_map = {
        'うらたぬき': 1,
        '志麻': 2,
        'あほの坂田。': 3,
        'となりの坂田。': 3,
        'センラ': 4,
    }
    return order_map.get(aname, 5)
  return 0.5


artist_song_list.sort(key=artist_sort_key)

# HTMLにJSONデータを埋め込んで出力
html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>現場まとめ App</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f8f9fa; padding-bottom: 60px; font-size: 14px; }}
        .nav-tabs .nav-link.active {{ font-weight: bold; border-bottom: 3px solid #0d6efd; }}
        .tour-card, .artist-card {{ background: white; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid #e9ecef; }}
        .tour-header, .artist-header {{ padding: 10px 15px; font-weight: bold; cursor: pointer; user-select: none; display: flex; justify-content: space-between; align-items: center; transition: opacity 0.2s; color: #212529 !important; }}
        .tour-header:hover, .artist-header:hover {{ opacity: 0.85; }}
        .header-usss {{ background-color: #b3e5fc; }}
        .header-urata {{ background-color: #c8e6c9; }}
        .header-shima {{ background-color: #e1bee7; }}
        .header-sakata {{ background-color: #ffcdd2; }}
        .header-senra {{ background-color: #fff9c4; }}
        .header-default {{ background-color: #e0e0e0; }}
        .tour-title, .artist-title {{ font-size: 0.95em; }}
        .live-row, .song-master-row {{ border-bottom: 1px solid #eee; transition: background 0.2s; }}
        .live-row:last-child, .song-master-row:last-child {{ border-bottom: none; }}
        .live-item-header {{ padding: 10px 15px; cursor: pointer; user-select: none; }}
        .live-item-header:hover {{ background-color: #f8f9fa; }}
        .live-title {{ font-weight: bold; color: #212529; font-size: 0.9em; }}
        .setlist-container {{ background: #fafafa; border-top: 1px solid #eee; padding: 10px 15px; }}
        .song-row {{ padding: 5px 0; border-bottom: 1px dashed #e0e0e0; display: flex; justify-content: space-between; align-items: center; }}
        .song-row:last-child {{ border-bottom: none; }}
        .medley-box {{ background: #f0f0f0; border-left: 3px solid #6c757d; margin: 6px 0; border-radius: 4px; }}
        .medley-title {{ padding: 6px 10px; font-weight: bold; font-size: 0.85em; cursor: pointer; color: #495057; }}
        .medley-sub-row {{ padding: 4px 10px 4px 20px; font-size: 0.82em; color: #555; display: flex; justify-content: space-between; border-top: 1px solid #e9ecef; }}
        .play-count {{ background: #e2e3e5; color: #41464b; border-radius: 10px; padding: 2px 8px; font-size: 0.75em; font-weight: bold; }}
        .badge-count {{ background: #6c757d; color: white; border-radius: 10px; padding: 2px 8px; font-size: 0.75em; }}
        .no-song-msg {{ color: #888; font-style: italic; font-size: 0.85em; text-align: center; padding: 8px; }}
        .live-check {{ width: 18px; height: 18px; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="container py-3" style="max-width: 800px;">
        <ul class="nav nav-tabs mb-3">
            <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab" href="#tab-lives">公演一覧 (<span id="lives-count-nav">0</span>)</a></li>
            <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#tab-songs">楽曲一覧 (<span id="songs-count-nav">0</span>)</a></li>
        </ul>

        <div class="tab-content">
            <div class="tab-pane fade show active" id="tab-lives">
                <div class="row g-2 mb-3">
                    <div class="col"><input type="text" id="search-input" class="form-control" placeholder="ツアー名・会場・日付で検索..." oninput="renderLives()"></div>
                    <div class="col-auto d-flex align-items-center">
                        <div class="form-check form-switch mb-0">
                            <input class="form-check-input" type="checkbox" id="attended-only-switch" onchange="renderLives()">
                            <label class="form-check-label small" for="attended-only-switch">参戦のみ</label>
                        </div>
                    </div>
                </div>
                <div id="lives-list-holder"></div>
            </div>

            <div class="tab-pane fade" id="tab-songs">
                <div class="row g-2 mb-3">
                    <div class="col"><input type="text" id="song-search" class="form-control" placeholder="曲名で検索..." oninput="renderSongs()"></div>
                    <div class="col-auto">
                        <select id="song-sort-order" class="form-select" onchange="renderSongs()">
                            <option value="asc">投稿日：古い順</option>
                            <option value="desc">投稿日：新しい順</option>
                        </select>
                    </div>
                </div>
                <div id="songs-list-holder"></div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    const tourList = {json.dumps(tour_list, ensure_ascii=False)};
    const liveToSongs = {json.dumps(live_to_songs, ensure_ascii=False)};
    const artistSongList = {json.dumps(artist_song_list, ensure_ascii=False)};

    function getAttendance() {{
        try {{ return JSON.parse(localStorage.getItem('usss_attended_lives') || '{{}}'); }}
        catch(e) {{ return {{}}; }}
    }}

    function toggleAttendance(liveId, ev) {{
        ev.stopPropagation();
        const att = getAttendance();
        if (ev.target.checked) {{ att[liveId] = true; }}
        else {{ delete att[liveId]; }}
        localStorage.setItem('usss_attended_lives', JSON.stringify(att));
        updatePlayCounts();
        renderSongs();
    }}

    let attendedPlayCounts = {{}};
    function updatePlayCounts() {{
        const att = getAttendance();
        attendedPlayCounts = {{}};
        for (const liveId in att) {{
            const songs = liveToSongs[liveId] || [];
            songs.forEach(s => {{
                if (s.is_medley) {{
                    s.medley_songs.forEach(ms => {{
                        attendedPlayCounts[ms.id] = (attendedPlayCounts[ms.id] || 0) + 1;
                    }});
                }} else {{
                    attendedPlayCounts[s.id] = (attendedPlayCounts[s.id] || 0) + 1;
                }}
            }});
        }}
    }}

    function getHeaderClass(artist) {{
        if (!artist) return 'header-default';
        if (artist.includes('うらたぬき')) return 'header-urata';
        if (artist.includes('志麻')) return 'header-shima';
        if (artist.includes('坂田')) return 'header-sakata';
        if (artist.includes('センラ')) return 'header-senra';
        if (artist.includes('浦島坂田船')) return 'header-usss';
        return 'header-default';
    }}

    function renderLives() {{
        const searchKw = document.getElementById('search-input').value.trim().toLowerCase();
        const attendedOnly = document.getElementById('attended-only-switch').checked;
        const att = getAttendance();
        const holder = document.getElementById('lives-list-holder');
        holder.innerHTML = '';

        let totalLivesCount = 0;

        tourList.forEach((tour, tIdx) => {{
            const filteredLives = tour.lives.filter(live => {{
                const matchKw = !searchKw || live.search.includes(searchKw);
                const matchAtt = !attendedOnly || att[live.id];
                return matchKw && matchAtt;
            }});

            if (filteredLives.length === 0) return;
            totalLivesCount += filteredLives.length;

            const headerClass = getHeaderClass(tour.artist);
            const tourCard = document.createElement('div');
            tourCard.className = 'tour-card';

            const tourHeader = document.createElement('div');
            tourHeader.className = `tour-header ${{headerClass}}`;
            tourHeader.setAttribute('data-bs-toggle', 'collapse');
            tourHeader.setAttribute('data-bs-target', `#tour-collapse-${{tIdx}}`);
            tourHeader.innerHTML = `
                <span class="tour-title">${{tour.tour_name}}</span>
                <span class="badge badge-count">${{filteredLives.length}}公演</span>
            `;

            const collapseDiv = document.createElement('div');
            collapseDiv.id = `tour-collapse-${{tIdx}}`;
            collapseDiv.className = searchKw ? 'collapse show' : 'collapse';

            const livesList = document.createElement('div');
            filteredLives.forEach((live, lIdx) => {{
                const isChecked = att[live.id] ? 'checked' : '';
                const liveRow = document.createElement('div');
                liveRow.className = 'live-row';
                liveRow.innerHTML = `
                    <div class="live-item-header d-flex justify-content-between align-items-center" data-bs-toggle="collapse" data-bs-target="#live-setlist-${{tIdx}}-${{lIdx}}">
                        <div>
                            <div class="live-title">${{live.date}} ${{live.venue}}</div>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <input type="checkbox" class="form-check-input live-check" ${{isChecked}} onclick="toggleAttendance('${{live.id}}', event)">
                        </div>
                    </div>
                    <div id="live-setlist-${{tIdx}}-${{lIdx}}" class="collapse setlist-container">
                        ${{renderSetlistHTML(live.id)}}
                    </div>
                `;
                livesList.appendChild(liveRow);
            }});

            collapseDiv.appendChild(livesList);
            tourCard.appendChild(tourHeader);
            tourCard.appendChild(collapseDiv);
            holder.appendChild(tourCard);
        }});

        document.getElementById('lives-count-nav').innerText = totalLivesCount;
    }}

    function renderSetlistHTML(liveId) {{
        const songs = liveToSongs[liveId] || [];
        if (songs.length === 0) return '<div class="no-song-msg">セットリスト情報がありません</div>';

        return songs.map(s => {{
            if (s.is_medley) {{
                const subRows = s.medley_songs.map(ms => `
                    <div class="medley-sub-row">
                        <span>${{ms.title}}</span>
                    </div>
                `).join('');
                return `
                    <div class="medley-box">
                        <div class="medley-title">${{s.idx}}. メドレー / コーナー</div>
                        ${{subRows}}
                    </div>
                `;
            }} else {{
                return `
                    <div class="song-row">
                        <span>${{s.idx}}. ${{s.title}}</span>
                    </div>
                `;
            }}
        }}).join('');
    }}

    function renderSongs() {{
        const searchKw = document.getElementById('song-search').value.trim().toLowerCase();
        const sortOrder = document.getElementById('song-sort-order').value;
        const holder = document.getElementById('songs-list-holder');
        holder.innerHTML = '';

        let totalSongsCount = 0;

        artistSongList.forEach((artistGroup, aIdx) => {{
            let songs = artistGroup.songs.filter(s => !searchKw || s.search.includes(searchKw));
            if (songs.length === 0) return;

            songs.sort((a, b) => sortOrder === 'asc' ? a.date_num - b.date_num : b.date_num - a.date_num);

            totalSongsCount += songs.length;
            const headerClass = getHeaderClass(artistGroup.artist_name);

            const card = document.createElement('div');
            card.className = 'artist-card';

            const header = document.createElement('div');
            header.className = `artist-header ${{headerClass}}`;
            header.setAttribute('data-bs-toggle', 'collapse');
            header.setAttribute('data-bs-target', `#artist-collapse-${{aIdx}}`);
            header.innerHTML = `
                <span class="artist-title">${{artistGroup.artist_name}}</span>
                <span class="badge badge-count">${{songs.length}}曲</span>
            `;

            const collapseDiv = document.createElement('div');
            collapseDiv.id = `artist-collapse-${{aIdx}}`;
            collapseDiv.className = searchKw ? 'collapse show' : 'collapse';

            const songListDiv = document.createElement('div');
            songListDiv.style.padding = '5px 15px';

            songs.forEach(s => {{
                const count = attendedPlayCounts[s.id] || 0;
                const countBadge = count > 0 ? `<span class="play-count">${{count}}回</span>` : '';
                const songRow = document.createElement('div');
                songRow.className = 'song-row';
                songRow.innerHTML = `
                    <div>
                        <span style="font-weight: 500;">${{s.title}}</span>
                        <span style="font-size: 0.75em; color: #888; margin-left: 8px;">${{s.date}}</span>
                    </div>
                    <div>${{countBadge}}</div>
                `;
                songListDiv.appendChild(songRow);
            }});

            collapseDiv.appendChild(songListDiv);
            card.appendChild(header);
            card.appendChild(collapseDiv);
            holder.appendChild(card);
        }});

        document.getElementById('songs-count-nav').innerText = totalSongsCount;
    }}

    document.addEventListener('DOMContentLoaded', () => {{
        updatePlayCounts();
        renderLives();
        renderSongs();
    }});
    </script>
</body>
</html>"""

with open('index.html', 'w', encoding='utf-8') as f:
  f.write(html_template)

print('Successfully generated index.html!')