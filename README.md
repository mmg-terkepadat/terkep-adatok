# terkep-adatok

Havonta frissülő közérdekű-hely kivonatok (patika, posta, bolt, étterem, szállás…) az OpenStreetMap adataiból.

- Forrás: [Geofabrik](https://download.geofabrik.de/) országos kivonatai.
- Futás: GitHub Actions, minden hónap 3-án (kézzel is indítható: Actions → „Térképadatok havi frissítése” → Run workflow).
- Eredmény: a **data-latest** kiadás fájljai (`manifest.json`, `hu-poi.sqlite.gz`, `com-XX.json.gz`).

Adat: © OpenStreetMap közreműködők, [ODbL](https://opendatacommons.org/licenses/odbl/). A kivonatok ugyanezen licenc alatt használhatók.
