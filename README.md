# GTA VI News Center — monitor e pubblicazione su X

**Produzione attiva · 18 novembre 2026.** Questo repository pubblico
supporta il canale X collegato a Buffer. Le automazioni operative sono
elencate in [OPERATIONS.md](OPERATIONS.md) e la gestione delle credenziali
in [SECURITY.md](SECURITY.md).

**Editoriale:** comunicati ufficiali, testate specializzate, link ai video
Rockstar e speciali PowerPyx su trofei, platino e progressione. Tutti i nuovi
post devono essere in italiano, con emoji pertinenti, spaziatura leggibile,
attribuzione e link. Nessuna ripubblicazione integrale di guide, foto o
video di creator. I contenuti PowerPyx sono segnalati come provenienti
dalla testata, non come conferme Rockstar.

**Fonti della community:** il progetto dispone di un nuovo [registro delle fonti GTA VI](COMMUNITY-RESEARCH-v1.md) e di un [ricercatore read-only](community_research_v1.py). PowerPyx resta una fonte già attiva per l'editoriale; GTA Series Videos viene analizzato tramite feed pubblico per preparare nuove guide e notizie, mentre GTAForums, GTA Wiki/Fandom, GTABase, GTANet, Tez2 e Jason Schreier sono fonti per ricerca e corroborazione, **non conferme ufficiali**. La scansione della community produce soltanto una coda GitHub per verifica; separatamente l'Editorial Autopilot può pubblicare automaticamente i **titoli di video GTA VI / GTA Online** provenienti dal feed pubblico verificato di GTA Series Videos, con attribuzione 'video community (non ufficiale)', deduplicazione e filtri anti-rumor. Non copia i filmati né li presenta come Rockstar.

**Budget:** nessun nuovo abbonamento né API X a pagamento. L'account Buffer
può avere un piano già pagato: consultare la propria dashboard prima della
scadenza, senza presume rinnovi. Commenti e retweet nativi non sono
automatizzati; sono disponibili [bozze manuali per X](OUTREACH-X-PLAYBOOK.md).

## Stato attuale e manutenzione

| Parte | Dove |
| --- | --- |
| Workflow di produzione | .github/workflows |
| Sorgenti PowerPyx e filtro dedupe | editorial_autopilot_v137.py |
| Ledger e storico cifrato (non cancellare) | .state |
| Procedure e monitoraggio | OPERATIONS.md |
| Sicurezza / credenziali | SECURITY.md |
| Bozze per risposte video su X | OUTREACH-X-PLAYBOOK.md |

**La sezione sottostante è documentazione storica di onboarding.**
Alcune istruzioni (come creare ex novo un account Free o attivare il
primo collegamento) non descrivono lo stato odierno del bot.
Per la gestione della produzione seguire i file aggiornati sopra.

---

## Guida storica iniziale


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

### Coda editoriale GitHub autonoma (novembre 2026)

Lo scanner `gta6-community-research-v1.yml` crea/aggiorna una singola GitHub Issue chiamata `GTA VI - Coda fonti community`. Contiene titoli, link e data delle fonti consultate, classificati (rumor, datamining, community e guida indipendente) ma **non** afferma di aver letto gli articoli e **non** accede a Buffer. Aggiornamenti e pubblicazioni sono separati; i post del canale X restano soggetti a traduzione, limiti, dedupe e controllo dei destinatari. Se il permesso GitHub Issues non è disponibile, l'Action fallisce e il digest rimane come artifact. Non è un sistema automatico di riscrittura del sito: i claim non verificati non vengono inseriti nel portale.

### Diagnostica autonoma e limiti reali

Il workflow `.github/workflows/gta6-bot-health-v1.yml` gira due volte al giorno, legge lo stato degli Actions di bot e sito e verifica il canale Buffer/X in **sola lettura**. In caso di errore, aggiorna/riapre una sola issue `GTA VI - Bot Health Alerts`, senza pubblicare, re-inviare o ri-autorizzare alcun post; quando il controllo ritorna sano, chiude l'avviso. I Quick Tips già sospesi restano sospesi finché non vengono verificati manualmente. L'accesso al repository non contiene token Buffer negli artifact.

Questo insieme di workflow e dei controlli è indipendente dalle conversazioni ChatGPT, ma non è letteralmente eterno: GitHub può disattivare gli scheduler su repository pubblici inattivi, gli API provider possono cambiare e le credenziali scadere. Le issue di salute servono a rendere visibili le anomalie mentre i job vengono eseguiti; non possono notificare da sole un arresto totale di GitHub Actions.


## Revisione automatica delle guide (senza invenzione di prove)

`guide_evidence_review_v1.py` analizza i titoli dei feed pubblici di **PowerPyx, GTA Series Videos e GTABase** ogni quattro ore. Raggruppa le segnalazioni per argomento (trucchi, glitch, trofei, missioni, veicoli, collezionabili, HDR), suggerisce quali pagine del sito confrontare e allega una checklist alla stessa Issue editoriale già esistente. Non apre nuove Issue per ogni notizia.

**Limiti documentati:** due notizie che parlano genericamente di veicoli non confermano lo stesso metodo o glitch. Le segnalazioni del feed non costituiscono prova dei passaggi, della patch o dello stato dei trofei. Per questo i campi `claim_verified`, `platform_verified`, `patch_verified`, `trophy_safe_verified` e `ready_to_publish` rimangono tutti `false`: nessuna guida, codice o articolo viene aggiornato automaticamente **nei suoi fatti** senza un sistema di verifica dei dettagli. Il sito può aggiornare automaticamente soltanto i collegamenti alle fonti pertinenti, chiaramente etichettati come non verificati. Anche i rumor sono mantenuti come piste, ma restano fuori dall'editoriale automatico X.

GTABase dispone di un endpoint RSS news indicato da strumenti pubblici di monitoraggio; viene controllato in sola lettura. Se non risponde in GitHub Actions, il guasto viene registrato, senza aggirare protezioni o interrompere gli altri feed. GTAForums e le wiki collaborative restano in verifica manuale finché non avremo un accesso pubblico strutturato valido e rispettoso dei loro sistemi.



## Continuità dei workflow programmati

La repository è pubblica: GitHub documenta la possibile disattivazione dei workflow `schedule` dopo **60 giorni senza attività** (<https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows>).

Per ridurre questo rischio il workflow `.github/workflows/gta6-schedule-keepalive.yml` esegue **un controllo settimanale**, ma crea un commit minimale nel solo file `.state/workflow-keepalive.json` **soltanto dopo almeno 35 giorni senza nuovi commit su `main`**. Usa `GITHUB_TOKEN` con il solo permesso GitHub `contents:write`; non legge o modifica Buffer, X, guide, trofei o contenuti editoriali e non richiede servizi esterni.

**Limiti:** questo sistema è preventivo e non garantisce che GitHub o i provider restino sempre disponibili, che tutti i run schedulati avvengano in orario o che GitHub continui a contare gli heartbeat automatici come attività idonea. Se GitHub disattiva il workflow prima dell'esecuzione, è necessario riabilitarlo manualmente. La manutenzione delle credenziali Buffer e dei feed rimane separata.



### Nuovo: GTA Wiki e verifiche delle guide

Il ricercatore GTA VI tenta anche il feed pubblico Atom delle modifiche di `gta.wiki`, senza confonderlo con Fandom e senza proclamare conferme: l'accesso è segnalato come `ok` o `unavailable` nella coda. `guide_claim_evidence_gate.py` valida dossier di prove per PS5, patch e trofei durante le scansioni ogni quattro ore, sempre **senza pubblicazione automatica di contenuti fattuali**. Il sistema non trasforma un titolo RSS in una guida trophy-safe. Maggiori dettagli in [COMMUNITY-RESEARCH-v1.md](COMMUNITY-RESEARCH-v1.md).


## Crescita organica X: un bot utile, non un feed di titoli

Il profilo @xFederiko11 ha un piano di crescita autonoma che non implica né promette follower automatici.

- **Publisher:** la selezione X ora evita video creator che riportano solo episodi numerati e non risolvono un problema; i video restano in Ricerca e sul sito. I contenuti che insegnano concretamente qualcosa restano candidabili. L'Editorial Autopilot passa a un massimo prudenziale di **6** prenotazioni/giorno e almeno **45 minuti** tra le sue prenotazioni; il monitor breaking/ufficiale rimane indipendente.
- **Coda giornaliera GitHub:** workflow GTA VI - Crescita X organica (solo bozze), senza X/Buffer API, genera un'unica Issue permanente con bio, post introduttivo da fissare, tre proposte originali che ruotano tra checklist trofei, HDR OLED, sicurezza dei glitch e ricerche community. Nessun post viene automaticamente inviato dalla coda.
- **Engagement umano:** risposte contestuali dopo aver visto davvero il contenuto, no bulk follow/like/reply, no engagement swap, nessun link non richiesto.
- **Metriche:** il report growth_metrics_v142.py separa prenotazioni/delivery Buffer dalle metriche X inserite manualmente nel CSV. Impressions e follower restano non disponibili finché non vengono rilevati realmente.
- **Quick Tips Buffer:** non vengono riattivati o aggirati. Nessuna nuova API, account o abbonamento.

Guida: [OUTREACH-X-PLAYBOOK.md](OUTREACH-X-PLAYBOOK.md). Per usare il profilo come porta d'ingresso al sito, inserire https://xfederiko11.github.io/gta-6/ nel campo **Sito web** di X e pubblicare/fissare manualmente il post introduttivo dall'Issue organica.

Le regole ufficiali X su automazione, contenuti duplicati e manipolazione della crescita sono referenziate nel playbook. Ridurre i post seriali può aumentare la qualità percepita, ma **non esistono metriche X che provino già un aumento dei follower**.


## X: Community Italia e sicurezza per l'account appena creato

Il pianificatore organico GitHub propone ogni giorno **cinque ricerche X in lingua italiana**, con argomento, domanda da cercare e suggerimento su come contribuire in modo pertinente. Non si tratta di singoli post già verificati: si aprono nell'app X e **solo l'utente** sceglie se rispondere, citare o fare repost. Se il revisore inserisce un post già letto in `data/x-conversation-candidates-v1.json`, il link e la bozza di risposta vengono mostrati nella stessa Issue, senza pubblicazione automatica. Questa funzione non possiede credenziali X, Buffer, API di follower o permessi di interazione.

A causa del profilo molto recente e del volume elevato registrato il 19 novembre 2026, i quattro workflow che possono inviare tramite Buffer condividono ora un **limite prudenziale volontario di 8 invii/prenotazioni nelle 24 ore mobili e 90 minuti di distanza minima**. Non sono soglie ufficiali di X, non contano i post manuali e non garantiscono immunità da restrizioni. Ricerca, fonti e sito restano attivi anche quando il coordinatore trattiene nuovi post. Un audit statico interrompe gli invii se vengono rimossi i controlli fondamentali. Le bozze promozionali del piano organico vengono trattenute quando il volume registrato è alto.

**Procedure, limiti, politica X e pausa d'emergenza:** [X-COMMUNITY-SAFETY.md](X-COMMUNITY-SAFETY.md). L'account non deve ricorrere a servizi follower, reply di massa, like automatici o bot IA per risposte non richieste. Buffer Quick Tips rimane in pausa.


## Piano launch boost autonomo (dal 19 novembre 2026)

I precedenti 4 invii automatizzati in 24 ore si sono rivelati un freno eccessivo per un portale GTA VI appena lanciato. Il coordinatore condiviso ora consente **fino a 8 prenotazioni/invii nelle 24 ore mobili**, con **almeno 90 minuti** tra una prenotazione e la successiva, fino al **29 novembre 2026 incluso** (UTC). Dal **30 novembre** scende automaticamente a **6/24 ore e 120 minuti**, senza bisogno di interventi manuali.

È un limite **volontario**, non imposto o approvato da X. Non comprende i post manuali e un thread Buffer può contenere più tweet. Se le prenotazioni degli ultimi giorni superano il budget, le fonti continuano a essere monitorate ma le pubblicazioni vengono trattenute; non si svuotano né riciclano i ledger. Il canale non fa follow, reply, like o repost automatici di utenti esterni. Le connessioni sono sempre manuali.

### Nuova rubrica automatica dalle guide del sito

`site_evergreen_posts_v1.py` aggiunge al normale Editorial Autopilot una serie **di 10 post originali distinti** che valorizzano le guide GTA VI già costruite: HDR per codice TV, sfide 100%, registrazione veicoli, studio animali, viaggio taxi, poligoni, meditazione Capitolo 1, checklist trofei, avvisi sui trucchi PS5 e scoperte community.

Il bot ne seleziona al massimo **uno al giorno**, dopo aver confermato che il permalink del sito risponda **200** con `canonical` esatto; in caso di pagina non disponibile non pubblica un link rotto. Usa chiavi stabili e lo stesso ledger di tutti gli altri post, per non ripetere una guida già utilizzata. Sono testi informativi (non affermazioni sullo stato della patch né sulle metriche X). La preview Open Graph è ospitata direttamente nel nostro sito.

La serie si integra con **55 schede trofei**, notizie RSS verificate, post Rockstar e gallerie. L'Editorial Autopilot può riservare al massimo **5 post al giorno nel proprio ledger**, lasciando spazio agli altri workflow nel tetto globale di otto. I Quick Tips Buffer rimangono sospesi. L'Issue #42 continua ad aggiornare una coda di ricerche italiane per risposte **manuali e contestuali**.

### Priorità del bot

1. Monitoraggio ufficiale e verifica delle notizie sempre attivi.
2. Pubblicazione di notizie ufficiali e aggiornamenti importanti entro il tetto globale.
3. Contenuti originali del sito: un estratto utile al giorno con fonte verificabile.
4. Trofei e progressione: schede individuali, senza pubblicare lo stesso requisito due volte.
5. Altri articoli editoriali selezionati, senza trasformare il feed X in una raffica di titoli copiati.

Non promettiamo crescita né immunità da ban: l'obiettivo è mantenere qualità, varietà e cadenza sostenibile usando soltanto GitHub e Buffer già collegato.


### Social Desk: apri un post e rispondi davvero, senza reply bot

L'Issue [Crescita organica X #42](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/42) contiene adesso, oltre ai post originali e alle cinque ricerche, una selezione giornaliera di **quattro account GTA/PlayStation** osservati nelle schermate dell'utente. Per ciascuno trovi link al profilo, ricerca mirata ai suoi post, condizioni per intervenire e un esempio in italiano o inglese **da adattare solo se il post reale è pertinente**.

Per i singoli post già letti e inseriti nel repository dal revisore, il bot può costruire un **Web Intent di risposta** precompilato. Questo apre soltanto il modulo di X: l'invio finale è sempre umano. Non utilizziamo API X, browser automation, likes/repost/follow automatizzati o risposte automatiche non richieste. Leggi [X-COMMUNITY-SAFETY.md](X-COMMUNITY-SAFETY.md) per la guida operativa.


### Social Radar X: tweet verificati e risposte pronte (opt-in)

Il nuovo workflow Social Radar X effettua una ricerca giornaliera tramite l'**API ufficiale X** e aggiorna la [Issue #48](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/48) con fino a **cinque post recenti identificati per URL esatto**, un estratto e una bozza di risposta italiana o inglese da copiare oppure aprire nella finestra Rispondi di X. **Non mette like e non invia risposte automaticamente.** Per utilizzare l'API a consumo occorre impostare un limite di spesa su X Developer Console, aggiungere il secret X_BEARER_TOKEN e abilitare la variable X_SOCIAL_RADAR_ENABLED=true. Senza queste azioni il workflow non effettua richieste a pagamento né inventa tweet. Documentazione completa in [X-COMMUNITY-SAFETY.md](X-COMMUNITY-SAFETY.md).


### Ripristino pubblicazione e monitoraggio Buffer (19 novembre)

Il direttore ha una finestra di recupero limitata a **cinque nuove prenotazioni in 24 ore dal 19/11 alle 20:45 UTC**, conservando 90 minuti di distanza fra le pubblicazioni, history e deduplicazione. Questo permette di riprendere dopo una raffica pregressa di oltre 30 registrazioni nei ledger senza disattivare i controlli. Passata la finestra torna il normale tetto 8/24h, poi il taper del 30/11.

L'audit **sola lettura** degli stati reali Buffer (ultimi 15 Sent/Scheduled/Error) è nella [Issue #50](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/50). Il Social Radar [Issue #48](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/48) ha anche un **fallback gratuito RSS→oEmbed ufficiale X**: solo permalink ritrovati in feed affidabili e verificati tramite embed pubblico, senza API X a consumo. Non garantisce 5 post al giorno, non ricerca tutto X e non mette cuori o commenti automatici. La ricerca completa con X API rimane opzionale, con opt-in e limite di spesa.

## Foto PS5 da X: coda di revisione (21 novembre 2026)

- La nuova Action `gta6-photo-review-inbox-v1.yml` esegue ogni giorno test e prepara un unico Issue editoriale riutilizzabile. I visitatori del sito **non** necessitano di GitHub: possono inviare una foto con la bozza X del modulo pubblico.
- La **ricerca X ufficiale è disattivata per impostazione predefinita**. Si avvia soltanto quando la variabile del repository `X_PHOTO_INTAKE_ENABLED=true`, il secret già esistente `X_BEARER_TOKEN` è disponibile e l'esecuzione è `schedule` oppure `workflow_dispatch: scan`. L'API potrebbe avere costi: configurare prima un limite nel portale X Developers e verificare l'autorizzazione del titolare. Una sola richiesta recent-search per esecuzione.
- La modalità gratuita controlla soltanto URL esatti già forniti dalla redazione in `data/photo-intake-known-status-v1.json` via l'oEmbed pubblico ufficiale, senza eseguire scraping, login o ricerca totale del social. Lista inizialmente vuota: nessuna scoperta automatica promessa.
- Il bot **non scarica foto, non pubblica su X, non approva diritti e non modifica il sito**. I candidati sono link di possibile interesse: l'Issue richiede revisione manuale di immagine, titolarità, permesso esplicito, testo e spoiler. Solo la successiva PR con WebP locale e hash SHA-256 può aggiornare `xFederiko11/gta-6`.
- Monitoraggio e regressione: `photo_review_inbox_v1.py`, `test_photo_review_inbox_v1.py`; nessuna nuova dipendenza, nessuna credenziale inserita nel repository.

## Copertine X uniche, per ogni link GTA VI Italia (21 novembre 2026)

- Il sito genera una **cover JPEG 1200x630 unica per ogni URL canonico**. Le meta Open Graph / Twitter rimandano al file `/assets/social-cards/{SHA256-percorso-primi-16}.jpg`, con titolo editoriale e, solo se il download ufficiale ZIP è disponibile, uno sfondo promozionale Rockstar. I contenuti di gioco documentati continuano a richiedere screenshot reali distinti.
- L'Autopilot allega la **cover specifica dell'articolo** per gli owned link (guide, trofei, playlist), anziché ripetere tre foto generiche. La funzione `social_media_gate_v2.py` impedisce al medesimo media URL di finire in post differenti nello stesso ledger e rifiuta sorgenti di terzi non autorizzate.
- **Foto vera obbligatoria prima di Buffer:** l'URL dell'immagine deve rispondere 200, content-type image valido e magic bytes JPEG/PNG/WebP. Se la foto manca, è già usata o la didascalia non permette il media, l'Autopilot non pubblica un post solo testo e non ritenta un invio di esito incerto. I post senza immagine di fonti esterne vengono trattenuti per revisione, senza riciclare loghi.
- Lo ZIP `GTAVI_Artwork_Wallpapers.zip` è facoltativo nella build Pages e non un lasciapassare a riutilizzare asset terzi commercialmente; serve come artwork illustrativo e non prova di una missione. Ogni URL ha comunque una cover originale e diversa anche se il download Rockstar fallisce.
- I workflow di X diversi dall'Editorial Autopilot rimangono separati: monitorarne i messaggi e gli allegati prima di affermare copertura completa di *tutti* i post. Nessun cambiamento a password, Buffer channel, numero giornaliero massimo, sincronizzazione PSN, licenze o auto-approvazione dei contributi.

Per il monitor ufficiale Rockstar/PlayStation è ora attivo anche il registro persistente `image_registry_v12.py` tramite `V12_UNIQUE_IMAGES: 'true'` nel workflow `gta-monitor.yml`. Quando il logo o la foto è stata già usata, l'evento va in revisione: non viene ripostato con la stessa immagine. Il canale può pubblicare meno aggiornamenti rispetto a prima, ma non spreca slot con lo stesso visual.
