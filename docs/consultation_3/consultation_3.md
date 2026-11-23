# Consultation 3 - Support Documentation

## Vytvaranie indexu

Index môžeme vytvárať rôznymi spôsobmi podľa toho, aký veľký a dynamický je systém. V praxi existujú tri hlavné prístupy k budovaniu indexu:

**A) Batch / Statická indexácia (Naše riešenie):**

Ako funguje: Index sa vytvorí naraz (jednorazovo) prečítaním celého datasetu (TSV súboru) pred tým, ako začneme nad ním vyhľadávať. Keď pribudnú nové dáta, index sa buď zmaže a postaví odznova, alebo sa aplikácia reštartuje.

Prečo sme sa pre ňu rozhodli: Pre náš projekt (statický zber 17 652 hier z BGG) je to najjednoduchší, najstabilnejší a najrýchlejší prístup. Ako si videl v logoch, postavenie celého indexu pre takmer 18-tisíc hier trvá v Pythone v pamäti len necelé 3 sekundy (18:43:03 až 18:43:06). Rebudovať ho po každom spustení je absolútne bezbolestné.

**B) Inkrementálna indexácia (Incremental Indexing):**

Ako funguje: Systém beží nepretržite. Keď crawler stiahne novú hru, indexer ju hneď pridá do existujúcej štruktúry bez toho, aby prerábal celý index od začiatku.

Kedy sa používa: Pri veľkých webových vyhľadávačoch (Google, Bing), kde weby pribúdajú každú sekundu a prebudovávať celý internet by trvalo príliš dlho. Pre školský projekt je to zbytočne komplexné.

**C) Real-time / Segmentová indexácia (napr. Elasticsearch / Lucene):**

Ako funguje: Zmeny sa zapisujú do malých dočasných segmentov na disku, ktoré sa pozadia zlučujú (tzv. segment merging).

## Other IDF Methods

Aké sú iné metódy IDF?

**A. Probabilistic IDF (Pavel-Sparck Jones IDF):**

Vzorec: IDF = log((N - DF) / DF)

Používa sa v pokročilých modeloch ako BM25. Ak slovo obsahuje viac ako polovica dokumentov, táto formula môže vyústiť do záporných čísel, čo sa v niektorých systémoch ošetruje.

**B. Global Frequency IDF / Max IDF:**

Počíta sa pomer maximálnej frekvencie termínu v korpuse voči jeho DF.