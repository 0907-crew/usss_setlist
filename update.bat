@echo off
chcp 65001 > nul
echo ====================================
echo 1. Pythonスクリプトを実行してHTMLを生成中...
echo ====================================
python generate_html.py
echo python end

echo.
echo ====================================
echo 2. 変更をGitHubへ送信中...
echo ====================================
git add .
git commit -m "Data update"
git push origin main

echo.
echo ====================================
echo ✅ 送信完了！ Netlifyが自動更新を開始しました。
echo    1分ほどでWebサイトに反映されます
echo ====================================
pause