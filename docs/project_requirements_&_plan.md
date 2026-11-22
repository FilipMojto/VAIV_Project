# Zoznam projektov

## Požiadavky na každý projekt
- **Programovací jazyk:** Java, Python, Shell scripting (niekedy stačí použiť nástroje ako Pig, GATE, OpenNLP, Spark, Avro, Parquet).
- **Dáta:** Od začiatku zvolené dáta, ktoré sa budú spracovávať v rozsahu minimálne **500 MB** alebo viac ako **1 milión záznamov** (väčšinou však niekoľko GB).
  - *Hlavné dáta:* Wikipédia EN
  - *Ostatné (len ako doporučené):* Slovenská Wikipédia SK, Freebase, YAGO, MAG

---

## Konzultácie
- Konzultácie po termíne sú za **0 bodov**.
- Všetko, s čím idete na konzultáciu, **musí byť na wiki**.
- **Komunikácia (email):** `martin.seleng@savba.sk`, `martin.druzbacky@stuba.sk`
- **HINT:** `[[user:meno.priezvisko:site_name]]` (bez medzier)

### Štruktúra vašej wiki (podstránky)
- `start`
- `1. Konzultacia`
- `2. Konzultacia`
- `1. Odovzdanie`
- `3. Konzultacia`
- `4. Konzultacia`
- `5. Konzultacia`
- `2. Odovzdanie`

---

## Harmonogram konzultácií a odovzdaní

### Konzultácia 1 – Výber a potvrdenie projektu + dáta
- **Termín:** `30. 09. 2026`
- Opis projektu – stručný prehľad (TLDR) + motivácia.
- Odkaz na stránky, ktoré idete scrapovať + aké dáta sú pre vás zaujímavé.
- Odkaz na wiki stránky, ktoré budete pripájať k vašim dátam + aké dáta sú pre vás zaujímavé.
- Minimálne 5 párov otázok a odpovedí, aké si predstavujete, že má váš systém prijímať a čo má „odpovedať“.

---

### Konzultácia 2a – Návrh riešenia
- **Termín:** `14. 10. 2026`
- Aké frameworky chcete používať?
- Diagram architektúry vášho crawl systému (ukážka).
- Aké hlavičky používate, aký timeout/sleep?
- Implementácia crawlera + zopár už stiahnutých stránok.

---

### Konzultácia 2b
- **Termín:** `28. 10. 2026`
- Dokončený crawler.
- Stiahnuté všetky dáta + štatistika (počet, veľkosť na disku).
- Dokončený extraktor (REGEX) + ukážky na wiki.
- Vlastný indexer, minimálne 2 metódy výpočtu „idf“ – ranku výsledkov.
- **BONUS:** Jednoduché unit testy (aspoň na 20 stránkach) na vaše REGEX extraktory.
- **BONUS:** Pridať do štatistiky aj počet tokenov `tiktoken`.

---

### Odovzdanie prvej časti projektu
- **Termín:** `28. 10. 2026` *(vlastná podstránka na odovzdanie!)*
- Odovzdanie má byť vo forme **„reportu“**, kde musíte stručne opísať, čo ste robili, a stručne okomentovať každý bod odovzdania. *Čo nie je na wiki, nebude hodnotené.*

#### Kapitoly/Sekcie, ktoré musí obsahovať odovzdanie:
- Opis projektu, čo je cieľom.
- Odkaz na stránky, ktoré ste scrapovali + aké dáta ste extrahovali (5 ukážok).
- Minimálne 5 párov otázok a odpovedí, aké si predstavujete, že váš systém bude prijímať a čo má odpovedať.
- Aké frameworky a knižnice ste použili a prečo.
- Architektúra vášho crawlovacieho systému, vrátane diagramu.
- Tabuľka s ukážkou vašich metadát, ktoré si ukladáte pri crawlovaní – ak si neukladáte metadáta, tak dôvod.
- Odôvodnenie použitých hlavičiek, timeoutov, sleepov.
- Ukážka vášho reálneho (nie pseudokódu) implementovaného kódu na extrakciu URL z HTML + ideálne aj preklik do reálneho kódu.
- Ukážka vášho reálneho (nie pseudokódu) implementovaného kódu na extrakciu entít z HTML/text/md + ideálne aj preklik do reálneho kódu.
- Opis vami vytvoreného indexera a INDEXU (TF), koľkokrát ho vytvárate atď.
- Opis vami implementovaných metód výpočtu „idf“.
- Ukážka porovnania správania jednotlivých metód výpočtu „idf“ na aspoň 3 vstupných dopytoch (queries).
- Tabuľka so štatistikou vami vycrawlovaných dokumentov – počet, veľkosť na disku, koľko z nich je relevantných pre váš projekt.
- ZIP súbor s kódom.
- **BONUS:** Súbor so všetkými unit testami na vaše REGEX extraktory.
- **BONUS:** Doplnenie štatistiky o počet tokenov.

---

### Konzultácia 3: Spracovanie „veľkých“ dát
- **Termín:** do `11. 11. 2026`
- Rozšíriť kód z prvého odovzdania na spracovanie dát, prechod na distribuované spracovanie (**Apache Spark**).
- Extrahovať a spracovať dáta (vrátane wiki dumpu) pomocou Sparku.
- Práca s wiki dátami (pomocou REGEX-ov).
- Odôvodniť a ukázať „join“ medzi vami extrahovanými dátami a dátami z wiki:
  - Koľko unikátnych wiki stránok ste pripojili.
  - Aké atribúty z wiki sú pre vás zaujímavé.

---

### Konzultácia 4: Lucene index
- **Termín:** do `25. 11. 2026`
- Hotový Spark kód (wiki, extrahované dáta, join).
- Návrh a implementácia indexu pomocou **PyLucene**.
- Odôvodnenie jednotlivých polí (fields) v indexe.
- Implementácia nového indexu do vašej aplikácie.
- Porovnanie dopytov (queries): starý index vs. nový index.
- Aké typy dopytov (queries) v indexe využívate (napr. Boolean – AND/OR, Range, Phrase, Fuzzy)?
- **ODKAZ NA GITHUB** (s vaším aktuálnym kódom).

---

### Konzultácia 5 – Evaluácia
- **Termín:** do `09. 12. 2026`
- Hotový softvér (aj na GitHube) + prezentovanie výsledného riešenia.
- Vyhodnotenie výsledkov vyhľadávania:
  - Porovnanie vašich výsledkov s vyhľadávaním na Google a na doméne, ktorú ste crawlovali.
  - Výsledky prezentované v textovej podobe (nie ako obrázky).

---

### Odovzdanie druhej časti projektu
- **Termín:** do `09. 12. 2026` *(vlastná podstránka na odovzdanie!)*
- **Architektúra distribuovaného spracovania (Apache Spark):**
  - Stručný opis prechodu na Spark – ako ste rozšírili kód z prvého odovzdania.
- **Spracovanie Wikipedia Dumpu:**
  - Opis, ako ste extrahovali a čistili dáta z Wiki dumpu.
- **Integrácia dát (The Join):**
  - Odôvodnenie a logika „joinu“: Ako a prečo ste spojili vami crawlované dáta s dátami z Wikipédie.
  - Štatistika prepojenia: Koľko unikátnych wiki stránok sa podarilo pripojiť k vašim dátam.
  - Zoznam atribútov z Wikipédie, ktoré ste sa rozhodli indexovať, a prečo sú pre váš projekt zaujímavé.
- **Indexovanie (PyLucene):**
  - Návrh schémy indexu: Zoznam všetkých polí (fields), ktoré indexujete.
  - Odôvodnenie jednotlivých polí a ich typu.
  - Aké typy dopytov (queries) využívate?
- **Vyhodnotenie a porovnanie:**
  - *Starý vs. Nový index:* Porovnanie výsledkov vyhľadávania (kvalita, rýchlosť, relevantnosť) medzi vaším riešením z 1. odovzdania a aktuálnym PyLucene riešením.
  - *Vaše riešenie vs. Google/Doména:* Porovnanie vašich výsledkov s vyhľadávaním na Google (resp. search barom na crawlovanej doméne) pre aspoň 5 rôznych dopytov. Výsledky prezentujte v prehľadnej tabuľke (textová podoba, nie screenshoty).
- **Odkaz na GitHub:**
  - ODKAZ NA GITHUB a ZIP súbor s kódom.