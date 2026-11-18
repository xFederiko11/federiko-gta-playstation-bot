# Editorial Autopilot v13.7 - Operativita e controlli

**Attivato dal workflow:** `.github/workflows/gta6-editorial-autopilot-v137.yml`.

## Cosa fa

Il workflow segue gli avvii pianificati e riusciti di `GTA Monitor gratuito` e dispone anche di un calendario diretto di backup; un push del workflow su main esegue il controllo iniziale.
I candidati provengono dai feed RSS di VGC, Push Square, IGN, GameSpot,
Everyeye e Multiplayer.it (vedi `editorial-autopilot-v137-sources.json`).
Pubblica fino a **1 post per run, 16 al giorno**, con **12 minuti minimi** fra
prenotazioni, e solo articoli con data non precedente a 12 ore. I limiti
possono ridurre il numero di post per evitare spam; l'avvio dipende dai ritardi GitHub.

I testi riportano la testata e il titolo attribuito, URL originale e hashtag.
Le notizie non sono trattate come conferme Rockstar.
Il sistema non copia immagini, non traduce articoli e non riporta rumor o leak.

## Sicurezza

1. `AUTO_PUBLISH=true` abilita il monitor e il nuovo Editorial Autopilot;
   `AUTO_PUBLISH=false` ferma l'invio editoriale automatico.
2. `EDITORIAL_AUTOPILOT_V137_ENABLED=false` mette in pausa solo questa funzione.
   Il valore assente lascia il modulo abilitato quando `AUTO_PUBLISH=true`.
3. Il workflow verifica l'account Buffer `xFederiko11` **prima** di riservare.
4. La prenotazione viene committata in `.state/editorial-autopilot-v137.json`
   prima della chiamata di pubblicazione. I risultati incerti NON vengono
   ritentati in automatico. Non cancellare il registro.
5. Controllare i log: `FEED_OK`, `FEED_ERROR`, `FEEDS`, `RESERVE count`,
   `BUFFER_SENT`, `BUFFER_PENDING` o `BUFFER_ERROR`.
   Un run verde senza `BUFFER_SENT` non equivale ad aver pubblicato.
6. In `Actions > GTA VI - Editorial Autopilot v13.7` la scelta
   `preview` non invia nulla; `run` puo inviare un nuovo post.

**Nota:** i vecchi workflow di bootstrap, test draft, launch pulse e bridge
sono stati rimossi per alleggerire Actions. I relativi script e registri
restano nel repository come storico/audit. Il Breaking Watch v13.4 e il
GTA Monitor rimangono attivi.

### Limiti intenzionali

- Non c'e un servizio di fact-check dei dettagli contenuti negli articoli.
- Non vengono generati video, immagini con diritti incerti o retweet.
- Il numero di post dipende dalla disponibilita dei feed e dai filtri.
- Le quote Buffer e i ritardi degli scheduler possono limitare le consegne.
- Aggiornare periodicamente le fonti RSS e i filtri per evitare errori.
