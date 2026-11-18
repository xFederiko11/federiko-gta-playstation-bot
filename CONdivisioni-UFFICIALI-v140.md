# Condivisioni ufficiali GTA VI senza nuovi abbonamenti — v14.0

## Decisione economica

**Nessuna API X a pagamento, nessun nuovo servizio, nessun account aggiuntivo.**
Riutilizza GitHub Actions, la connessione Buffer già configurata e il feed
RSS/Atom pubblico del canale YouTube ufficiale Rockstar Games:

`https://www.youtube.com/feeds/videos.xml?channel_id=UC6VcWc1rAoWdBCM0JxrRQ3A`

## Cosa fa

- Controlla i video dal canale ufficiale Rockstar già incluso in `sources.free.json`.
- Pubblica, attraverso il monitor già esistente, un testo **interamente in
  italiano**, con blocchi vuoti tra introduzione, messaggio, link e hashtag.
- Condivide il **link al video originale** su X, senza scaricare o copiare
  file multimediali e senza riutilizzare fotografie di altri creator.
- Usa il registro esistente: un evento già pubblicato non viene ripetuto.
  Con una risposta Buffer incerta si blocca la ripetizione automatica.
- Usa il flag `OFFICIAL_LINKS_FREE_ENABLED=true` dichiarato direttamente
  nel workflow `gta-monitor.yml`, senza richiedere nuovi repository secrets
  o variabili. Continua a rispettare `AUTO_PUBLISH`.

**Non è un retweet nativo di X.** I link al video originale possono ottenere
un'anteprima, ma non c'è una garanzia di player incorporato. La nuova funzione
non monitora l'intera timeline di `@RockstarGames`; l'API X e gli scraping
fragili restano esclusi.

## Sicurezza

- Il feed è già presente ed è marcato con `trust: official` e con l'ID
  specifico del canale Rockstar.
- Per condividere un video, il link deve essere `youtube.com/watch?v=...`
  oppure `youtu.be/...` e l'evento deve essere classificato **GTA VI** o
  **GTA Online**.
- Non spacciamo video di terzi per video Rockstar e non traduciamo
  automaticamente i titoli inglesi non verificabili: usiamo descrizioni
  brevi e italiane che non inventano dettagli.
- La pubblicazione richiede sempre una notizia **nuova**, non l'archivio
  precedente all'attivazione.
- Per spegnere solo la condivisione video, rimuovere dal workflow
  `OFFICIAL_LINKS_FREE_ENABLED: 'true'` oppure impostarlo a `'false'`.
- La programmazione GitHub può subire ritardi e Buffer potrebbe rifiutare
  singoli post: controllare `Buffer Sent` e la scheda invii di X.

## Verifica

Esegui `python -m unittest -q test_official_links_free_v140`.

Il test controlla: provenienza ufficiale, 280 caratteri, link e righe vuote,
invio senza chiamare API di traduzione o caricare immagini, ed assenza di
ripubblicazione al secondo passaggio.
