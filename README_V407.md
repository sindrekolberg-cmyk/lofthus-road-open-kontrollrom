# Lofthus Road Open V407

Polish/fix release based on V406.

- Hall of Fame language corrected: `sesongtitler` and `månedsseier/månedsseire`.
- `Månedskonger` remains the navigation/category name.
- Aggregate `pallplasser` removed from Hall of Fame ranking rows.
- Mesterrekorder made defensive against an older/cached `HistoryStore`; verified Nordmo history is available as a fallback.
- Front page keeps August winner until September has actual points, then changes automatically to September leader.
- Stat wording uses full `poeng`.
- League table rebuilt in the same visual language as the rest of the site, while keeping click-to-sort headers including +/-.
- Hall of Fame > Sesonger tables now use the same flat sports-table style rather than native Streamlit dataframes.
