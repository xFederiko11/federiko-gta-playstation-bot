# 🤖 Bot X — Stato operativo

Aggiornato: 25 novembre 2026, 23:36 CET (ultimo controllo produzione). Consegna tra sessioni, non registro storico. Ricontrollare GitHub prima di agire: lo stato reale prevale.

## Ripartenza
- Sito: https://xfederiko11.github.io/gta-6/ — repository [gta-6](https://github.com/xFederiko11/gta-6).
- Bot: questo repository; X @xFederiko11 tramite Buffer. Fuso Europe/Rome.
- Applicare le istruzioni permanenti. Nessun nuovo costo, risposta automatica a terzi o richiesta di permessi a creator/editori. Nessun invio forzato.
- Leggere main, PR, Actions, registri e configurazioni. Implementare, testare, integrare e verificare. Svolgere attività indipendenti durante le QA; non ripetere lavoro concluso.
- Tutorial lineari, tema scuro, copertina JPEG 1200×630 condivisa, fonti e controlli per passaggio, diritti documentati, video opt-in, canonical invariati. Ispezione articolo intero 390/1440 px prima dell'autorizzazione ai rilanci.

## Prossime tre priorità
1. **P0 — [PR sito #138](https://github.com/xFederiko11/gta-6/pull/138).** Ramo riallineato dopo #137, head 316cfd4a6e6e7e66cdb77b15c6c2b3e1c55c15a8. QA combinata [#45714409445](https://github.com/xFederiko11/gta-6/actions/runs/45714409445) ancora in fase browser; verificare risultato effettivo, integrare solo se positivo. Verificare deploy, artifact e schermate integrali 390/1440 delle guide 70 sfide, poligoni e Randy. Autorizzare singolarmente solo dopo verifica editoriale e visiva; completare 13/13 e allineare social.
2. **P1 — Schede Randy e Advanced Tracker.** Nuovi walkthrough PowerPyx ricontrollati il 25/11: https://www.powerpyx.com/gta-6-randys-wish-list-car-locations-walkthrough/ e https://www.powerpyx.com/gta-6-how-to-register-advanced-tracker-cars/. Catalogo ancora da modificare. Priorità: Vitello (indizio Waning Sands, garage), Infernus (indizio Crosstown, settimo piano), Tempesta (Vespucci Island, distinguere precedente mappa GTABase). Verificare anche Toros e Windsor Drop prima di cambiare stato/noindex. Aggiornare data/vehicle_catalog_v1.json, test e catture delle pagine modificate; poi salvare-auto (Dale Mamba) e social coerenti. Non garantire spawn, non inventare ricompense, lasciare aperta discrepanza Coquette D10.
3. **P2 — Autonomia e qualità.** Verificare produzione X, vetrina creator, primi rilanci eleggibili, acquisizione ufficiale patch e fotografie autorizzabili. Usare candidati read-only per contenuti concreti; ricontrollare SEO solo con evidenze. Nessuna riduzione dei gate per aumentare frequenza.

## Stato e fonti di verità
- Sito: PR #136 e #137 integrate; main 68c05d523178537b405c70dddb5a0c6bf3e9a096. Deploy [#45714315533](https://github.com/xFederiko11/gta-6/actions/runs/45714315533) interamente riuscito; marker PUBLIC_ACTION_FIRST_MOSES_OK, PUBLIC_ANIMALS_REVIEW_OK, PUBLIC_TAXI_REVIEW_OK alle 22:35:12 UTC. Artifact 15064358713 già ispezionato, contenuti invariati dalla #136. Moses, animali e taxi completati.
- Bot: [PR #186](https://github.com/xFederiko11/federiko-gta-playstation-bot/pull/186) integrata, commit 436f172ffd6438cace4eabed9b60fdbac7ac03cc. QA #45714582507: 512 test, OK, uno saltato; crescita #45714582443 riuscita. Produzione #45714692860 riuscita.
- Rilanci: site-article-rotation-v1.json, site_article_rotation_v1.py, ARTICLE-ROTATION-PLAN.md. 10/13 autorizzati su main, enabled=true. Mancano 70 sfide, poligoni, Randy. Cooldown 7/14/30 giorni, max uno/dì, gate live/copertina/Sent. Moses senza precedente Sent nel ledger; rilancio bloccato. Nessuna approvazione in massa.
- Produzione: .state/editorial-autopilot-v137.json e data/x-permalinks-v1.json. Ultimo ciclo #45714692860: 86 contenuti, zero errori feed, zero nuovi tentativi, ricevuta Sent confermata alle 22:36:54 UTC con immagine. Tre Sent il 25/11; vetrina creator e rilanci non confermati, X pubblico non verificato indipendentemente. Obiettivo 5–6/dì, 07–23, gap 120 min; evergreen max uno/dì e 20h. Creator poi archivio patch. Non abbassare i gate media.
- Fonti: monitor-health.json e history-public.json. Monitor #45714152585, report 22:35:04 UTC: Newswire/YouTube/PS5 senza errori, Support GTA SourceError, Support GTA VI ReadTimeout, PS4 nessun errore registrato. Storico: 4 registrazioni, zero osservazioni patch automatiche. Parser e import sito già integrati. Ultima patch documentata 23/11, nessun proxy a pagamento.
- Fotografie: 189 materiali Rockstar, 158 copertine distinte, 55 ruoli fotografici; nessuna nuova foto autentica approvata. Dieci screenshot senza permessi esclusi (#134). Ricerca read-only #45702531180, 45 candidati.
- SEO: indice guide indicizzato; homepage/HDR/trofei scansionati non indicizzati, patch/Moses/animali/taxi sconosciuti a Google all'ultima ispezione. Canonical e robots corretti per pagine note; OpenSEO/Search Console in lettura.
- Evidenze editoriali: fonti, decisioni, test e procedure sono nel codice, nelle PR e in ARTICLE-ROTATION-PLAN.md. Nessun gameplay o riproduzione video dichiarati verificati senza prova reale.

## Chiusura di ogni sessione
Report breve: completato, verificato, da risolvere, massimo tre priorità. Aggiornare **questo stesso file su main** solo se cambia lo stato utile alla ripartenza, sostituendo le priorità concluse; mantenere circa 40 righe senza cronologia, credenziali o informazioni personali. Rileggere il file e usare il blob SHA corrente per evitare sovrascritture concorrenti. Non modificare configurazioni o avviare workflow solo per aggiornare la consegna. Questo file è documentazione, non configurazione eseguibile. I job autonomi seguono la normale pianificazione.
