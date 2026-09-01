# Lofthus Road Open V601

Deploy compatibility hotfix for V600.

- `app.py` no longer hard-crashes if Streamlit/GitHub temporarily serves an older `lro_history.py` without `hall_of_fame_sort_key`.
- The V600 Hall of Fame hierarchy is preserved through an in-app fallback.
- The full V600 module set is included and should be uploaded together to the repository root.
- Existing `data/` must remain untouched.
