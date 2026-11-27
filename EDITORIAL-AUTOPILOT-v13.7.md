# Editorial Autopilot v13.7 - Operativita e controlli

**Attivato dal workflow:** `.github/workflows/gta6-editorial-autopilot-v137.yml`.

## Cosa fa

Il workflow segue gli avvii pianificati e riusciti di `GTA Monitor gratuito` e dispone anche di un calendario diretto di backup; un push del workflow su main esegue il controllo iniziale.
I candidati provengono dai feed RSS di VGC, Push Square, IGN, GameSpot,
Everyeye e Multiplayer.it (vedi `editorial-autopilot-v137-sources.json`).
Pubblica fino a **1 post per run, 6 al giorno**, con **45 minuti minimi** fra
prenotazioni, e solo articoli con data non precedente a 12 ore. I limiti
possono ridurre il numero di post per evitare spam; l'avvio dipende dai ritardi GitHub.

I testi riportano la testata e il titolo attribuito, URL originale e hashtag.
Le notizie non sono trattate come conferme Rockstar.
Il sistema non copia immagini e non riporta rumor o leak.

## Media per singolo contenuto

- La verifica dei diritti riguarda la singola immagine, pagina e destinazione. Una foto senza prova applicabile viene esclusa; non ferma gli altri contenuti.
- Se un articolo RSS supera i controlli editoriali ma non ha una foto autorizzata, il bot può condividere soltanto il suo URL originale, senza allegati, con attribuzione e host verificato. La preview eventuale è generata da X dal link esterno; il bot non scarica né carica miniature.
- Come fallback iniziale è consentito un solo post con il link al video ufficiale Rockstar già verificato. La copia e l'eventuale thread sono allowlist esatte e deduplicate; la condivisione non autorizza il download, l'allegato o l'embed della thumbnail.
- Per gli articoli del sito usare il player YouTube su richiesta del lettore e mappe esterne. Una foto si allega solo quando `photo_rights_v1` documenta i diritti per quella immagine, contenuto e canale.
- Il tetto editoriale è **6 post originali al giorno**, con almeno 45 minuti tra prenotazioni; le ore operative sono 07:00–23:00 locali. Non ridurre qualità per riempire gli slot.

## Stile editoriale obbligatorio (v13.8)

**Tutti i nuovi post su X devono essere interamente in italiano**, inclusi quelli
ricavati da testate inglesi e dagli avvisi ufficiali Rockstar. Le fonti
rimangono inglesi quando il loro nome e un nome proprio, ma i titoli sono
tradotti prima di creare il post. Non viene tradotto o copiato l'articolo
integrale.

Formato obbligatorio: titolo e categoria, riga bianca, informazione principale
in italiano, riga bianca, attribuzione e URL fonte, riga bianca, massimo
due hashtag pertinenti. Max 280 caratteri pesati secondo X.

Se la traduzione fallisce, elimina numeri, altera nomi propri o presenta
ancora inglese, il post viene **trattenuto**, mai pubblicato in inglese.
Un controllo aggiuntivo del monitor principale trattiene testi in inglese
anche all'ultimo passaggio prima di Buffer. Lo stesso vale per i link ai
video ufficiali. La rassegna RSS usa MyMemory solo sui titoli gia pubblici;
la disponibilita, i limiti d'uso e la qualita di tale servizio possono
ridurre la frequenza editoriale. Non inviare a servizi esterni credenziali
o informazioni private.

La regola riguarda i **nuovi** invii: non modifica post gia pubblicati o
gia programmati nella coda Buffer. Continua a distinguere fatti confermati
e fonti di stampa senza presentare indiscrezioni come comunicati ufficiali.

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
