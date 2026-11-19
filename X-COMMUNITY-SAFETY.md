# GTA VI · Community Italia e protezione account X

## Obiettivo e stato

Il bot conserva la ricerca **autonoma** su GitHub, l'aggiornamento del sito e la pubblicazione di notizie verificate con Buffer. La nuova funzione **Community Italia** è diversa: prepara collegamenti a ricerche X italiane da aprire manualmente, senza autenticarvisi, senza recuperare i singoli post e **senza** automatizzare risposte, like, repost, citazioni, DM, follow o unfollow.

I link in `organic_growth_v1.py` derivano dalle ricerche tematiche definite in `x_community_review_v1.py`, con cinque suggerimenti ogni giorno e rotazione delle nicchie. L'Issue GitHub già esistente [GTA VI - Crescita organica X](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/42) si aggiorna senza creare issue ripetitive. Un risultato di ricerca **non è un post verificato** e non è una richiesta di contatto. X può richiedere accesso all'app per mostrare i risultati.

### Come usare la coda

1. Apri l'Issue #42 da telefono e scegli una delle ricerche italiane. Non esistono quote di risposte da completare.
2. Apri il *post originale* che tratta realmente una domanda GTA VI, trofei, glitch o PS5. Leggi il contesto e controlla data, patch e piattaforma se la risposta contiene dati tecnici.
3. Se hai un contributo utile, scrivilo **tu** direttamente nell'app X, in italiano. Evita risposte quasi identiche a più autori; niente link al sito se il contesto non lo richiede.
4. Per citare/repostare un post, usa le funzioni X **manualmente**, dopo averne letto la fonte. Non usare Buffer come falso retweet: un post con URL non è un Quote Post nativo.
5. Se vuoi conservare un post per la revisione, inserisci in `data/x-conversation-candidates-v1.json` il permalink originale e il contesto letto. **Non è necessario** farlo per partecipare normalmente alle discussioni.

### Post specifici, solo se letti da una persona

Il file versionato `data/x-conversation-candidates-v1.json` inizia con `{"schema":"gta6-x-conversations-v1","posts":[]}`.

Un record accettabile, dopo aver davvero consultato il post nell'app, ha questi campi:

```json
{
  "post_url": "URL reale https://x.com/ACCOUNT/status/NUMERO",
  "language": "it",
  "reviewed_original": true,
  "reviewed_utc": "2026-11-19T15:00:00+00:00",
  "original_context": "Descrizione fedele di cosa scrive e chiede realmente il post originale",
  "editorial_note": "Motivo specifico per il quale una risposta aggiungerebbe valore",
  "draft_reply_it": "Risposta originale da controllare manualmente prima di inviarla"
}
```

Le URL devono riferirsi a un **post X effettivo**, non a ricerche o profili generici. L'esempio non è un post reale, è soltanto un modello da sostituire. Non inserire dati privati, non copiare lunghi passaggi non propri. Il sistema controlla domini, ID numerico, duplicati, data, lingua e motivazione; **non verifica automaticamente che l'affermazione sia vera né invia la bozza**. È consentito lasciare `draft_reply_it` vuoto.

## Coordinamento reale delle pubblicazioni

I quattro workflow che usano Buffer sono:

- `gta-monitor.yml` — novità Rockstar e PlayStation, con ricerca sempre attiva;
- `gta6-editorial-autopilot-v137.yml` — selezione editoriale italiana;
- `gta6-special-campaign-v139.yml` — campagne/gallerie;
- `launch-watch-v134.yml` — notizie ufficiali urgenti.

Con `EDITORIAL_DIRECTOR_V142_ENABLED: 'true'`, tutti passano da `editorial_director_v142.allowed()`. Le soglie di cautela adottate **volontariamente** per un account nuovo sono:

- **4 prenotazioni/invii automatizzati nelle 24 ore mobili** tra i quattro workflow.
- **Almeno 3 ore** tra due prenotazioni automatiche nel registro condiviso.
- Anche tentativi pendenti o incerti contano per prudenza; nessun secondo invio automatico dello stesso tentativo.
- I thread possono contenere **più tweet** e le pubblicazioni manuali non entrano nei ledger del bot: 4 è un numero di *invii registrati*, non un conteggio garantito di post X.
- Se raggiunge un limite, **non spegne la ricerca**. Blocca soltanto nuove prenotazioni per la consegna e lascia i workflow aggiornare le fonti come previsto.

Non sono **limiti ufficiali** di X e non garantiscono assenza di filtri, shadowban o sospensioni. Un contatore di Buffer non è una misura di visibilità o reputazione del profilo. La coda di crescita sospende anche le proposte di nuove bozze promozionali quando il volume recente è elevato.

`x_automation_safety_v1.py` controlla prima della pubblicazione che tutti i workflow mantengano il coordinatore, lo stesso gruppo di concorrenza, il comportamento senza cancellazione dei runner durante l'invio e la separazione da Community Italia. Le verifiche sono **statiche**: non possono certificare che X ritenga sicuro l'account. Se un audit fallisce, il job deve interrompersi prima di chiamare Buffer.

## In caso di avviso «Sblocca di più su X» o effettive restrizioni

Il messaggio ricevuto nel profilo non prova da solo shadowban. Evita azioni rapide e ripetitive, servizi che offrono follower, account multipli coordinati e reply automatici. Se appare una richiesta di verifica, segui soltanto i passaggi dell'app ufficiale.

Se vuoi **mettere in pausa tutti gli invii automatici**, usa le variabili GitHub Actions della repository: imposta `AUTO_PUBLISH=false` e separatamente `LAUNCH_WATCH_V134_AUTOPUBLISH=false`. Non cancellare i ledger o disinstallare strumenti. Le azioni `workflow_dispatch` con parametro esplicito `run` sono una scelta manuale distinta e non vanno usate durante la pausa. Le scansioni e le queue continuano a funzionare, purché il workflow le preveda. Verifica la dashboard Buffer per eventuali post già in coda: spegnere gli invii futuri su GitHub **non annulla** post che Buffer ha già accettato.

Manteniamo `TIPS_REAUTH_CONFIRMED_V149=false` salvo una conferma esplicita dell'utente, come già concordato.

## Regole ufficiali — controllate il 19 novembre 2026

Le [regole sull'automazione di X](https://help.x.com/en/rules-and-policies/x-automation), aggiornate nell'aprile 2026, autorizzano le pubblicazioni informative automatizzate entro altre condizioni, ma proibiscono le risposte automatiche non richieste generate su parole chiave. I bot che pubblicano **automaticamente risposte create dall'IA** necessitano di previa approvazione scritta di X. I repost automatici non sono vietati in assoluto, ma repost aggressivi o in blocco possono violare le regole. I like automatizzati sono vietati. Le [regole sull'autenticità](https://help.x.com/en/rules-and-policies/authenticity) scoraggiano spam, link ripetitivi e interazioni volte a manipolare le metriche.

**La funzione sviluppata non si avvale di eccezioni né tenta di aggirare limiti, verifica d'identità o misure anti-abuso.**
