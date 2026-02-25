# Пошук інфлюенсерів (Euphoria_fi + Polymarket 5 min)

Скрипт шукає в X (Twitter) авторів, які згадували **Euphoria_fi** або **Polymarket 5 min**, і збирає їх у CSV з охватами (followers, лайки, ретвіти).

## Як запустити

1. Встанови залежності:
   ```bash
   pip install -r requirements.txt
   ```

2. Ключі API вже в `.env`. Якщо створюєш з нуля — скопіюй `.env.example` в `.env` і встав свої Consumer Key та Consumer Secret з [X Developer Portal](https://developer.x.com/).

3. Запуск:
   ```bash
   python find_influencers.py
   ```

Результат: файл **influencers.csv** і вивід топ-15 за кількістю підписників у консолі.

### Повний аналіз і рекомендації (жива аудиторія)

```bash
python3 analyze_influencers.py
```

Скрипт збирає **тексти твітів** (що саме писали), рахує **engagement rate** (взаємодії / охват) і будує таблицю **recommendations.csv** з колонками:

- **recommendation** — Strong hire / Consider / Skip  
- **engagement_rate**, **total_engagement** — жива аудиторія  
- **recommendation_reason** — чому така оцінка  
- **sample_tweet_1, 2, 3** — зразки того, що вони писали  

Критерії: Strong hire = висока активність аудиторії (ER та мінімум взаємодій); Skip = мертва стрічка або боти (following >> followers, нуль лайків).

### Історичні твіти (окрема сторінка) — TwitterAPI.io, тільки Euphoria_fi

Офіційний X API дає лише **останні 7 днів** (і пошук може вимагати платного тарифу). Для історії — **окрема сторінка** лише по **Euphoria_fi** через [TwitterAPI.io](https://twitterapi.io/):

1. Додай у `.env`: `TWITTERAPI_IO_API_KEY=твій_ключ`.
2. Запусти пошук за періодом (тільки Euphoria_fi / euphoria.fi):
   ```bash
   python3 fetch_historical_twitterapi_io.py --since 2025-01-01 --until 2025-02-19
   ```
   Результат пишеться в **euphoria_historical.csv** (не в recommendations.csv).
3. Згенеруй окрему HTML-сторінку:
   ```bash
   python3 export_to_html.py euphoria_historical.csv
   ```
   Відкрий **euphoria_historical.html** — там заголовок «Euphoria.fi · Historical» і твіти за обраний період.

Головна сторінка **recommendations.html** залишається від основного потоку (X API, 7 днів, Euphoria + Polymarket). Історична сторінка — тільки для наочного тесту TwitterAPI.io по Euphoria_fi.

### Як поділитись recommendations.html (посилання для браузера)

Щоб сторінка відкривалась по посиланню як звичайний сайт (а не як сирцевий код):

1. **GitHub Pages** (рекомендовано)  
   - У репо [XKols](https://github.com/NZ3000s/XKols): **Settings** → **Pages**.  
   - **Source**: Deploy from a branch.  
   - **Branch**: `main`, folder **/ (root)** → Save.  
   - За 1–2 хвилини з’явиться посилання:
   - **https://nz3000s.github.io/XKols/recommendations.html**  
   Його можна відкривати в браузері і надсилати іншим — твіти будуть вбудовані, фільтри працюватимуть.

2. **Локально**  
   Відкрий файл у браузері: подвійний клік по `recommendations.html` або перетягни його у вікно Chrome/Safari. Посилання типу `file:///...` не варто надсилати — воно працює тільки на твоєму комп’ютері.

## Безпека

- Не публікуй і не коміть файл `.env` (він у `.gitignore`).
- Якщо ключі потрапили в публічний доступ — перегенеруй їх у Developer Portal.
