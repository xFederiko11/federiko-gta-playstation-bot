# GTA VI — Tips & Tricks immediati (v14.6)

## Obiettivo editoriale

Le guide PowerPyx possono essere molto lunghe anche quando un consiglio utile
si spiega in due o tre passaggi. La rubrica `quick_tips_v146.py` trasforma
**solo suggerimenti già verificati manualmente** in veri thread X composti da
**due messaggi collegati**.

### Messaggio 1 — soluzione immediata con foto
- Intestazione **GTA VI + parola chiave** (trofeo, 100%, PS5, platino).
- 1–3 passi concreti con pulsanti PS5, senza inventare impostazioni o timing.
- Vantaggio pratico, con emoji pertinenti e doppio a capo.
- Una **foto promozionale ufficiale Rockstar**, indicata come
  *illustrativa*, non schermata della meccanica.
- Fino a due hashtag SEO; **nessun link esterno che rubi spazio alle istruzioni**.

### Messaggio 2 — risposta al post principale
- Fonte dichiarata: **PowerPyx**.
- Link esatto all'articolo originale e nota di attribuzione dell'immagine.
- Il bot usa **una sola mutazione Buffer `publish_thread`**, con due elementi;
  la foto è collegata al primo, la fonte al secondo.
- Non viene inviata una risposta separata che potrebbe rimanere orfana.

## Sei consigli già verificati
1. WAiNK: scansione rapida veicoli (↑, R1), 200/277 per il 100%.
2. Binocolo: studio animali (↑, R1), 100/255 senza caccia.
3. Sfide: 70/80 per la checklist del 100%, con 10 da poter evitare.
4. Meditazione nel Capitolo 1: attività mancabile, impatto sul trofeo non
   ancora confermato da PowerPyx. Nessun dettaglio di storia rivelato.
5. Poligoni: incremento della statistica Concentrazione e 42 medaglie Oro.
6. Taxi: viaggio rapido disponibile dopo la prima missione, con chiamata Paradise Taxi e spesa di 100 $.

Fonte: articoli PowerPyx pubblicati il **18 novembre 2026**, link nel
secondo messaggio di ogni thread. Nessun paragrafo dell'articolo viene
copiato integralmente. I pulsanti PS5 sono riportati solo quando documentati.

## Programmazione, costi e sicurezza
- Pubblicazione tramite **Editorial Autopilot esistente**; nessuna Actions
  aggiuntiva, nessuna API X a pagamento, nessun nuovo abbonamento.
- Massimo **2 Tips & Tricks al giorno**, almeno **110 minuti** tra di loro,
  fermo restando il limite di **22 minuti** del Direttore Editoriale.
- Ledger condiviso `.state/editorial-autopilot-v137.json`, chiave stabile
  per ciascun trucco e prenotazione prima della chiamata Buffer.
- Se manca l'immagine ufficiale, l'articolo è bloccato; non si pubblica
  un thread senza foto o con link immagine di terzi.
- Se Buffer restituisce stato incerto non si ripete automaticamente.
- Nuovi trucchi possono essere aggiunti solo dopo controllo della guida,
  della patch, dei comandi e della provenienza dell'immagine. Non generare
  procedure automaticamente dal solo titolo RSS.
- Tutti i testi sono in italiano.

## QA prima della produzione

`python -m unittest -q test_quick_tips_v146`

I test verificano 280 caratteri pesati su ogni messaggio, fonte nella
risposta, asset solo sul primo elemento, una singola chiamata di scrittura,
assenza di ripubblicazione e vincoli giornalieri.

### Avvertenza
Una run GitHub verde non prova che entrambe le parti del thread siano
visibili su X. Controllare `BUFFER_SENT`, il thread e i media nella scheda
Sent di Buffer e poi sul profilo pubblico.
