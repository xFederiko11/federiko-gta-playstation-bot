# Federiko - GTA + PlayStation News Center: ricerca su X

Aggiornamento editoriale: 17 novembre 2026.

## Obiettivo

Rendere le notizie verificabili piu' facili da trovare nella ricerca X senza
forzare hashtag, parole trending o connessioni inesistenti tra fatti diversi.
Nessun algoritmo o hashtag garantisce posizionamento o visualizzazioni.

## Regole implementate

- GTA VI: nomi naturali **GTA VI** e **GTA 6**; tag `#GTAVI` e, se non c'e'
  una piattaforma specifica, `#GTA6`.
- GTA VI dichiarato per PS5: `#GTAVI #PS5`; per PS5 Pro **solo se citata
  esplicitamente**: `#GTAVI #PS5Pro`.
- GTA Online: `#GTAOnline`, eventualmente con un solo hashtag console.
- GTA V: `#GTAV`, eventualmente con un solo hashtag console.
- Firmware PS5: testo **Firmware PS5**, hashtag `#PS5 #PlayStation`.
- Firmware PS4: testo **Firmware PS4**, hashtag `#PS4 #PlayStation`.
- Aggiornamenti PS5 e PS4: `#PS5 #PS4`.
- Il firmware PlayStation **non** riceve `#GTAVI` se non riguarda GTA VI.
- Un massimo di **2 hashtag per singolo post**, nessun hashtag duplicato.
- Nei thread gli hashtag sono concentrati nel **primo** post.
- Titolo, fonte ufficiale, provenienza e limite **280 caratteri pesati** hanno
  la precedenza: i tag opzionali possono essere omessi quando non c'e' spazio.
- Per articoli community, demo o non verificati **non** vengono aggiunti tag
  di promozione. Le policy del bot devono comunque bloccarne l'invio automatico.
- Non vengono inventati release date, patch note, FPS, trofei, immagini o rumor.
- Nelle bozze singole ancora in attesa il testo viene rigenerato solo al momento
  del primo invio; post gia' pubblicati/accettati non vengono rispediti.

## Esempi

**Firmware Sony PS5** -> `PlayStation · SISTEMA`, `Firmware PS5`,
`#PS5 #PlayStation`. Nessun `#GTA6`.

**Annuncio GTA VI per PS5** -> `GTA VI (GTA 6) · NEWS`,
`#GTAVI #PS5`.

**Annuncio GTA VI comune** -> `GTA VI (GTA 6) · NEWS`,
`#GTAVI #GTA6`.

## Sicurezza e verifica

1. Lasciare la variabile Actions `AUTO_PUBLISH=false`.
2. Eseguire manualmente `check` e controllare le righe `ANTEPRIMA` / `BOZZA`.
3. Prima di pubblicare, valutare le vecchie bozze firmware ancora in coda;
   l'aggiornamento SEO **non** rimuove ne' approva quelle bozze.
4. Il codice non modifica i Secrets, il workflow GitHub o lo stato cifrato.
5. Nessun test di pubblicazione reale su Buffer/X e' incluso.

## Riferimenti

- https://help.x.com/it/using-x/how-to-use-hashtags
- https://help.x.com/en/rules-and-policies/x-search-policies
