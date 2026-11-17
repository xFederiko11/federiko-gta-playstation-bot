# GTA + PlayStation Monitor — online, gratuito, fonti ufficiali

Questa versione usa **GitHub Actions in un repository pubblico** per eseguire
il bot e **Buffer Free** per pubblicare su X. Segue le notizie comuni di GTA,
quelle PlayStation e le versioni del software di sistema PS5/PS4.
Non serve tenere acceso un PC,
non servono API OpenAI e non servono credenziali sviluppatore X.

Il progetto è pronto da caricare. Non è ancora collegato al tuo account e nessun
post reale è stato inviato durante la preparazione. Dopo la configurazione
iniziale, i controlli e i post nuovi sono automatici.

## Prima di iniziare

Ti servono il tuo account X e due account gratuiti: **Buffer Free** e **GitHub Free**.
Non inserire una carta di pagamento e non scegliere un piano a pagamento.
Il repository sarà pubblico: codice, immagini dei post e storico sono visibili.
Le chiavi restano nei Secrets GitHub; lo stato interno del bot è cifrato.

La disponibilità gratuita è stata verificata il 17 novembre 2026:

- [Buffer Free](https://buffer.com/pricing): fino a 3 canali e 10 post in coda per
  canale, con [API disponibili anche sul Free](https://support.buffer.com/en-us/articles/using-buffers-api-GtIYIQilz5).
  Per un canale, la quota è 1.000 richieste API ogni 30 giorni: letture e controlli
  di consegna contano, non solo i post. Il bot si ferma prima della quota con un
  tetto locale di 900 richieste/30 giorni e 40/giorno.
- [GitHub Actions](https://docs.github.com/en/actions/concepts/billing-and-usage):
  i runner standard sono gratuiti per i repository pubblici. Il workflow incluso
  usa questo caso e rifiuta l'esecuzione su repository privati.

La gratuità ha quindi limiti di volume e disponibilità. Il bot conserva le bozze
quando raggiunge un limite; non compra crediti e non cambia piano automaticamente.

## 1. Collega X a Buffer

1. Apri [Buffer](https://buffer.com/) e crea un account con il piano **Free**.
2. Vai in [Channels](https://account.buffer.com/channels), scegli **Connect Channel**
   e collega il tuo account **X/Twitter**. Accedi su X quando richiesto da Buffer.
3. Apri [Settings → API](https://publish.buffer.com/settings/api) e crea una chiave API.
4. Conservala: fra poco la inserirai in un campo protetto di GitHub. Non inviarla
   in chat e non metterla in un file pubblico.

Se il sito propone un upgrade, resta sul Free. La chiave del bot non è una
password X e non è una chiave sviluppatore X.

## 2. Crea il posto dove il bot lavorerà online

1. Apri [GitHub](https://github.com/) e accedi o crea un account **Free**.
2. Premi **New repository**. Come nome puoi usare `gta-monitor`.
3. Scegli **Public**, seleziona **Add a README file** e premi **Create repository**.
4. Scarica ed estrai lo ZIP del progetto fornito in chat.
5. Nel repository apri **Add file → Upload files**. Carica il **contenuto interno**
   della cartella estratta. `online.py`, `sources.py` e `README.md` devono apparire
   nella pagina principale, non dentro un'ulteriore cartella `gta6-bot`.
6. Includi la cartella `.github`: contiene il programma che lo avvia automaticamente.
   Poi premi **Commit changes**.

Per controllare che sia tutto al posto giusto, apri la scheda **Actions**:
deve comparire **GTA Monitor gratuito**. Se non compare, verifica che esista
il file `.github/workflows/gta-monitor.yml`. Puoi crearlo con **Add file → Create
new file**, usando esattamente quel percorso e copiando il file incluso nello ZIP.

Non caricare una cartella `.venv`, browser, vecchi database o un file `.env`.
Lo ZIP gratuito non li contiene.

## 3. Inserisci due dati protetti

Nel repository apri **Settings → Secrets and variables → Actions → Secrets**.
Premi **New repository secret** per ognuno di questi:

| Name | Secret da inserire |
|---|---|
| `BUFFER_API_KEY` | La chiave appena creata su Buffer |
| `STATE_PASSWORD` | Una nuova password lunga almeno 16 caratteri, dedicata al bot |

Salva `STATE_PASSWORD` nel tuo gestore di password. Serve a riaprire lo storico
interno e non va cambiata senza migrare lo stato esistente. Non è la password X.
GitHub fornisce da solo il token per salvare immagini e stato: non devi crearne uno.

## 4. Trova il canale X corretto

1. Apri **Actions → GTA Monitor gratuito → Run workflow**.
2. Nel menu **action** scegli **setup** e premi il pulsante **Run workflow**.
3. Apri l'esecuzione appena avviata, poi il passaggio
   **Raccogli, prepara le schede e pubblica se attivato**.
4. Nel risultato vedrai i tuoi canali Buffer con `id`, `name`, `service` e
   `externalLink`. Individua il tuo account X: il servizio è `twitter`.
5. Copia il suo valore **id**. Torna nei Secrets e crea:

| Name | Secret |
|---|---|
| `BUFFER_CHANNEL_ID` | L'ID del tuo canale X mostrato nel passaggio setup |

Questo passaggio legge l'account e non pubblica nulla. Se hai più canali,
controlla l'indirizzo X in `externalLink` prima di scegliere l'ID.

## 5. Fai il primo controllo

1. Torna in **Actions → GTA Monitor gratuito → Run workflow**.
2. Scegli **check** e avvia.
3. Attendi il completamento. La prima esecuzione salva i punti di partenza delle
   fonti e prepara lo storico: **non ripubblica tutte le vecchie notizie**.
4. Nella pagina principale del repository compariranno `history-public.csv`,
   `history-public.json`, `monitor-health.json` e lo stato cifrato `.state/bot.enc`.
5. Apri `history-public.csv`: GitHub lo mostra come una tabella.

Il primo controllo prepara anche un annuncio per ciascuna versione corrente
PS5/PS4 verificata sulla pagina Sony. Il titolo dice **disponibile**, senza
inventare la data di uscita. Le notizie GTA, invece, iniziano dalla baseline.
Le anteprime nella cartella `previews` marcate **DEMO** hanno dati fittizi e il
programma impedisce di pubblicarle. `ps5-system-demo.png` mostra il nuovo formato
per gli aggiornamenti del software di sistema.

Se una fonte fallisce, i log dicono quale. Il bot conserva gli ultimi dati validi:
un errore di rete non diventa un post di aggiornamento.

## 6. Attiva i post automatici

1. Apri **Settings → Secrets and variables → Actions → Variables**.
2. Premi **New repository variable**.
3. Imposta **Name** = `AUTO_PUBLISH` e **Value** = `true`.
4. Torna in Actions, avvia il workflow con **action = run**.

Da quel momento il workflow ricontrolla le fonti circa ogni **15 minuti** e
pubblica le novità rilevate dopo la baseline. Non devi riaprire questa chat o
lasciare aperta una pagina. Buffer può impiegare un po' a completare l'invio:
il bot distingue un post accettato da uno effettivamente pubblicato.

Se il primo `run` non trova novità, non inventa un post di prova. Puoi verificare
il collegamento X nella pagina Channels di Buffer e attendere un aggiornamento.

## 7. Come fermarlo o controllarlo

- Per fermare i post, cambia la variabile `AUTO_PUBLISH` da `true` a `false`.
  La raccolta e lo storico continuano.
- Per fermare anche la raccolta, in **Actions** apri il workflow, premi il menu
  **…** e scegli **Disable workflow**.
- Per vedere i post inviati e gli eventuali errori X, apri Buffer.
- Per controllare fonti e programma, apri l'ultima esecuzione di GitHub Actions.
- `monitor-health.json` mostra anche gli ultimi controlli e gli errori per fonte,
  senza chiavi o contenuti interni delle bozze.
- Per conservare una copia dello storico, scarica `history-public.csv`.

GitHub può ritardare i controlli programmati e disabilitare i workflow dopo
inattività prolungata. Non è un servizio con consegna garantita al minuto:
[documentazione della pianificazione](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).
Se viene disattivato, lo riattivi dalla scheda Actions.

## Fonti e contenuti seguiti

Il bot legge direttamente **Newswire Rockstar**, **Rockstar Support**, il
**canale YouTube ufficiale Rockstar** e le **pagine Sony del software di sistema**.
Il filtro controlla sia l'origine sia il contenuto: un'etichetta "ufficiale"
assegnata a un sito esterno non basta. Le segnalazioni community non sono ammesse.

Sono mantenuti gli annunci GTA comuni o riferiti a PlayStation. Le notizie e le
bozze relative esclusivamente a Xbox o PC sono escluse prima della pubblicazione.
La raccolta dal catalogo Microsoft è disattivata.

Il monitor Support segue nuovi articoli e revisioni delle patch note individuate
nell'indice. Una revisione è annunciata come **Patch note aggiornata**, senza
presentare tutte le vecchie correzioni nella pagina come una nuova patch.

### Software di sistema PS5 e PS4

Le pagine operative ufficiali sono:

- [Sony — informazioni sul software di sistema PS5](https://www.playstation.com/it-it/support/hardware/ps5/system-software-info/)
- [Sony — informazioni sul software di sistema PS4](https://www.playstation.com/it-it/support/hardware/ps4/system-software-info/)

Sono controllate circa ogni ora. Il programma legge solo HTML, senza scaricare
file firmware. Separa la versione corrente dalla sezione con gli aggiornamenti
precedenti: non prende un numero a caso e non usa gli screenshot come fonte.

La prima lettura crea una bozza per la versione corrente di ciascuna console;
poi viene creato un nuovo annuncio solo quando cambia la versione. Una modifica
alla grafica o al testo della pagina non genera un duplicato. Versione, novità
e link provengono da Sony; la data di lettura non diventa data di rilascio.

## Storico: solo informazioni ufficiali

Per GTA VI su PS5 rimane la disponibilità ufficiale del preload del **10 novembre
2026**. Le dimensioni e i numeri build non documentati da fonti ufficiali restano
mancanti: non viene inventata una prima versione `1.0`.

Lo storico pubblicato ora esclude sia Xbox sia i record `reported` della versione
precedente. Mantiene la distinzione fra disponibilità, spazio richiesto, download
e patch; ad esempio un requisito di spazio libero non diventa una dimensione di
download. Le versioni di sistema Sony verificate sono registrate con la data di
osservazione, separata da una data di rilascio eventualmente sconosciuta.

Il manifest GTA VI PS5 candidato non ha risposto in modo utilizzabile: il progetto
non dichiara verificata una cronologia completa di tutte le build scaricabili.

## Design e regola dei post per console

Le immagini sono generate localmente e gratis: formato 1600×900, fondo scuro,
accenti ciano/rosa, fonte e console leggibili. La stessa struttura viene riusata
automaticamente per ogni notizia.

- Una notizia comune che include PlayStation: **un post comune**.
- Dati PlayStation specifici o differenti: **post dedicati alla console**.
- Software di sistema PS5 e PS4: versioni distinte, **annunci separati**.
- Dati mancanti o frasi ambigue: nessuna falsa equivalenza; viene indicato ciò
  che non è disponibile.

Per evitare un servizio AI a pagamento, i testi usano regole e modelli locali.
Le etichette sono italiane; i titoli originali delle fonti possono restare in
inglese. Questa versione gratuita non fa OCR automatico e non interpreta video
o file di gioco. Gli spoiler ufficiali restano ammessi e i riferimenti narrativi
riconoscibili sono segnalati; non è un filtro spoiler garantito.

Le immagini da allegare devono essere raggiungibili da Buffer: il bot le salva
nel repository pubblico e passa l'URL HTTPS. Questo collegamento segue i requisiti
documentati, ma la consegna completa immagine → Buffer → X richiede la prova con
il tuo account, che non è stato collegato durante lo sviluppo.

## Limiti gratuiti e problemi riconoscibili

Il limite locale è 20 tentativi di pubblicazione/giorno, 40 richieste Buffer/giorno
e 900/30 giorni, inclusi controlli e richieste fallite. Le quote del servizio
rimangono vincolanti e possono cambiare. Quando una quota termina, si accumulano
bozze: non viene acquistato nulla per sbloccarle.

Se la connessione cade durante un invio e non si sa se il post sia uscito,
l'elemento resta `uncertain`: il bot evita il reinvio alla cieca. Se Buffer ha
già assegnato un ID, il bot ne controlla la consegna senza ricreare il post.
Eventuali elementi `review` richiedono il controllo nella dashboard Buffer.

| Problema | Cosa fare |
|---|---|
| Il workflow non appare | Verifica `.github/workflows/gta-monitor.yml` nella radice del repository |
| `STATE_PASSWORD` mancante | Aggiungi il Secret corretto, almeno 16 caratteri |
| Stato non decifrabile | Ripristina la password originale; non cancellare lo stato per tentativi |
| Canale Buffer non trovato | Ripeti `setup` e copia l'ID del canale X corretto |
| Canale scollegato/bloccato | Ricollega X in Buffer e poi riesegui `run` |
| Nessun post al primo avvio | Normale: è la baseline, non una ripubblicazione dello storico |
| Fonte non aggiornata | Consulta la fonte indicata nei log; le altre possono continuare |
| Quota esaurita | Attendi il rinnovo; nessun upgrade necessario o automatico |
| `uncertain` / `review` | Controlla il post e gli errori su Buffer prima di qualunque reinvio |

## Verifica del progetto

Sono verificati localmente: raggruppamento e separazione console, grafica,
storico e provenienza, stato cifrato, quote e invii simulati. Le pagine Sony,
Newswire e Support sono state lette dal vivo. Le chiamate autenticate
Buffer/GitHub e la consegna sul tuo account X non sono state eseguite: mancano
i tuoi account collegati e i relativi Secrets.

## Se hai già caricato la versione precedente

Carica i nuovi file nello stesso repository, mantenendo i Secrets e
`.state/bot.enc`. Il programma usa `history-ps-seed.json`, non importa resoconti
esterni e filtra anche le bozze precedenti non più ammesse. Il prossimo controllo
riscrive lo storico pubblico con i soli dati ufficiali PlayStation.
Gli invii già accettati da Buffer prima del cambio non vengono annullati dal filtro.
