# 🤖 Bot X — Stato operativo

Aggiornato: 26 novembre 2026, 00:10 CET (sessione operativa). Consegna tra sessioni, non registro storico. Ricontrollare GitHub prima di agire: lo stato reale prevale.

## Ripartenza
- Sito: https://xfederiko11.github.io/gta-6/ — repository [gta-6](https://github.com/xFederiko11/gta-6).
- Bot: questo repository; X @xFederiko11 tramite Buffer. Fuso Europe/Rome.
- Applicare le istruzioni permanenti. Nessun nuovo costo, risposta automatica a terzi o richiesta di permessi a creator/editori. Nessun invio forzato.
- Leggere main, PR, Actions, registri e configurazioni. Implementare, testare, integrare e verificare. Svolgere attività indipendenti durante le QA; non ripetere lavoro concluso.
- Tutorial lineari, tema scuro, copertina JPEG 1200×630 condivisa, fonti e controlli per passaggio, diritti documentati, video opt-in, canonical invariati. Ispezione articolo intero 390/1440 px prima dell'autorizzazione ai rilanci.

## Prossime tre priorità
1. **P0 — [PR sito #139](https://github.com/xFederiko11/gta-6/pull/139).** Head 1210846f86e9b694ab801dfae33bc08acbbc4b47; [QA #45719080353](https://github.com/xFederiko11/gta-6/actions/runs/45719080353) in corso (build). Aggiunge pass poligoni 5 GTA$ e menu di controllo, cinque schede Randy (Vitello/Waning Sands, Infernus/Crosstown, Tempesta/Vespucci Island, Windsor Drop/Bayside, Toros/Southside). Proposte 19/25 schede verificate, Windsor e Toros promossi sulla fonte, non ancora pubblicati. Integrare solo dopo QA e ispezione delle nuove catture 390/1440, quindi verificare deploy e marker PUBLIC_FINAL_GUIDE_REVIEW_OK (3 guide) e PUBLIC_RANDY_VEHICLE_OK (5 schede). 
2. **P1 — Completare 13/13 rilanci e allineare social.** PR #138 integrata, QA #45714409445 riuscita; artifact #15069367367 scaricato e ispezionate 12 schermate (tre guide, due dimensioni, procedura e approfondimenti). Deploy #45718493083 riuscito, ma accesso HTTP diretto alle tre URL via web non riuscito; #139 aggiunge controlli mirati post-deploy. Dopo #139 e nuova revisione poligoni autorizzare individualmente 70 sfide, poligoni e Randy; aggiornare testi obsoleti e schede auto nel bot. Proseguire salvare-auto/Advanced Tracker (Dale Mamba). Non garantire spawn, non inventare ricompense; discrepanza Coquette D10 aperta.
3. **P2 — Autonomia e qualità.** Verificare produzione X, vetrina creator, primi rilanci eleggibili, acquisizione ufficiale patch e fotografie autorizzabili. Usare candidati read-only per contenuti concreti; ricontrollare SEO solo con evidenze. Nessuna riduzione dei gate per aumentare frequenza.


## Stato e fonti di verità
- Sito: PR #136–138 integrate; main d5dcefac9a76cd4a1a3e84fc59b211426c5dec06. Ultimo deploy [#45718493083](https://github.com/xFederiko11/gta-6/actions/runs/45718493083) riuscito; regressioni Moses/animali/taxi escluse dai marker HTTP. Guide 70 sfide, poligoni e Randy aggiornate; verifica pubblica individuale e autorizzazioni pendenti. PR #139 aperta.
- Bot: [PR #186](https://github.com/xFederiko11/federiko-gta-playstation-bot/pull/186) integrata, commit 436f172ffd6438cace4eabed9b60fdbac7ac03cc. QA #45714582507: 512 test, OK, uno saltato; crescita #45714582443 riuscita. Produzione #45714692860 riuscita.
- Rilanci: site-article-rotation-v1.json, site_article_rotation_v1.py, ARTICLE-ROTATION-PLAN.md. 10/13 autorizzati su main, enabled=true. Mancano 70 sfide, poligoni, Randy; completare dopo #139. Cooldown 7/14/30 giorni, max uno/dì, gate live/copertina/Sent. Moses senza precedente Sent nel ledger; rilancio bloccato. Nessuna approvazione in massa.
- Produzione: .state/editorial-autopilot-v137.json e data/x-permalinks-v1.json. Ultimo ciclo #45714692860: 86 contenuti, zero errori feed, zero nuovi tentativi, ricevuta Sent confermata alle 22:36:54 UTC con immagine. Tre Sent il 25/11, zero nuove prenotazioni rilevate al cambio giorno; vetrina creator e rilanci non confermati, X pubblico non verificato indipendentemente. Obiettivo 5–6/dì, 07–23, gap 120 min; evergreen max uno/dì e 20h. Creator poi archivio patch. Non abbassare i gate media.
- Fonti: monitor-health.json e history-public.json. Monitor #45714152585, report 22:35:04 UTC: Newswire/YouTube/PS5 senza errori, Support GTA SourceError, Support GTA VI ReadTimeout, PS4 nessun errore registrato. Storico: 4 registrazioni, zero osservazioni patch automatiche. Parser e import sito già integrati. Ultima patch documentata 23/11, nessun proxy a pagamento.
- Fotografie: 189 materiali Rockstar, 158 copertine distinte, 55 ruoli fotografici; nessuna nuova foto autentica approvata. Dieci screenshot senza permessi esclusi (#134). Ricerca read-only #45702531180, 45 candidati.
- SEO: indice guide indicizzato; homepage/HDR/trofei scansionati non indicizzati, patch/Moses/animali/taxi sconosciuti a Google all'ultima ispezione. Canonical e robots corretti per pagine note; OpenSEO/Search Console in lettura.
- Evidenze editoriali: fonti, decisioni, test e procedure sono nel codice, nelle PR e in ARTICLE-ROTATION-PLAN.md. Nessun gameplay o riproduzione video dichiarati verificati senza prova reale.

## Chiusura di ogni sessione
Report breve: completato, verificato, da risolvere, massimo tre priorità. Aggiornare **questo stesso file su main** solo se cambia lo stato utile alla ripartenza, sostituendo le priorità concluse; mantenere circa 40 righe senza cronologia, credenziali o informazioni personali. Rileggere il file e usare il blob SHA corrente per evitare sovrascritture concorrenti. Non modificare configurazioni o avviare workflow solo per aggiornare la consegna. Questo file è documentazione, non configurazione eseguibile. I job autonomi seguono la normale pianificazione.
