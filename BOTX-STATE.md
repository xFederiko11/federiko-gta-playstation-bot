# 🤖 Bot X — Stato operativo

Aggiornato: 25 novembre 2026. Questa è la consegna tra sessioni, non un registro storico. Ricontrollare GitHub prima di agire; lo stato reale prevale sui dati qui riportati.

## Ripartenza
- Sito: https://xfederiko11.github.io/gta-6/ — repository [gta-6](https://github.com/xFederiko11/gta-6).
- Bot: questo repository; X @xFederiko11 tramite Buffer. Fuso Europe/Rome.
- Applicare le istruzioni permanenti del progetto. Nessun nuovo costo, risposta automatica a terzi o richiesta di permessi a creator/editori. Nessun invio forzato.
- Leggere main, PR, Actions, registri e configurazioni. Implementare, testare, integrare e verificare; svolgere attività indipendenti durante le QA. Non ripetere lavoro concluso.
- Tutorial lineari, tema scuro, copertina JPEG 1200×630 condivisa, fonti e controlli per passaggio, media con diritti documentati, video opt-in, canonical invariati. Verifica articolo intero a 390/1440 px prima dell'autorizzazione ai rilanci.

## Prossime tre priorità
1. **P0 — [PR sito #137](https://github.com/xFederiko11/gta-6/pull/137).** QA [#45709378638](https://github.com/xFederiko11/gta-6/actions/runs/45709378638) superata; PR ancora aperta. Integrare dopo ricontrollo head e QA. Verificare deploy completo e marker PUBLIC_ACTION_FIRST_MOSES_OK, PUBLIC_ANIMALS_REVIEW_OK, PUBLIC_TAXI_REVIEW_OK. La PR #136 è già integrata (4ad49cb); artifact 15064358713: sei schermate integrali Moses/animali/taxi già ispezionate. Il deploy #45709092054 ha pubblicato le pagine ma fallito il controllo finale sui vecchi iframe. Se contenuti invariati, riutilizzare le evidenze; autorizzare singolarmente le tre guide e allineare i testi social solo dopo verifica pubblica.
2. **P1 — [PR sito #138](https://github.com/xFederiko11/gta-6/pull/138).** QA [#45709620301](https://github.com/xFederiko11/gta-6/actions/runs/45709620301) superata; PR ancora aperta. Integrare dopo #137 preservando la correzione del workflow, verificare QA sul codice combinato, deploy, schermate integrali e approfondimenti a 390/1440. Revisionare e autorizzare 70 sfide, poligoni e Randy.
3. **P2 — Schede Randy e Advanced Tracker.** Verificare individualmente i nuovi walkthrough PowerPyx, aggiornare data/vehicle_catalog_v1.json e salvare-auto senza duplicati o spawn garantiti; tenere aperta la discrepanza Coquette D10. In parallelo verificare produzione X, acquisizione ufficiale patch e cause SEO reali.

## Stato e fonti di verità
- Sito: main 4ad49cb404043e5bcf42128217f6a5db744866cc; ultimo deploy completamente validato #45706666139. PR #137 head 4641e78; #138 head a6b4954.
- Bot: ultimo commit applicativo 52f5060; main precedente a questo documento 417eb18. QA precedente 511 test, OK, uno saltato.
- Rilanci: site-article-rotation-v1.json, site_article_rotation_v1.py, ARTICLE-ROTATION-PLAN.md. 7/13 autorizzati, enabled=true. Cooldown 7/14/30 giorni, max uno/dì, gate live/copertina/Sent. Le sei guide di P0/P1 restano non autorizzate. Nessuna approvazione in massa.
- Produzione: .state/editorial-autopilot-v137.json e data/x-permalinks-v1.json. Ultimo workflow #45706106268 riuscito. Tre Sent il 25/11, immagini presenti; vetrina creator e rilanci non confermati, X pubblico non verificato indipendentemente. 5–6 post/dì, 07–23, gap 120 min; evergreen max uno/dì e 20h. Creator poi archivio patch. Non abbassare i gate media.
- Fonti: monitor-health.json e history-public.json. Monitor #45705713398, 21:37:44 UTC: Newswire/YouTube/PS5 OK, Support GTA SourceError, Support GTA VI ReadTimeout, PS4 dato non recente. Parser patch e import sito già integrati, zero osservazioni patch automatiche. Ultima patch documentata 23/11; non dichiarare Support ripristinato. Nessun proxy a pagamento.
- Fotografie: 189 materiali Rockstar, 158 copertine distinte, 55 ruoli fotografici; nessuna nuova foto autentica approvata. Dieci screenshot senza permessi esclusi (#134). Ricerca read-only #45702531180, 45 candidati.
- SEO: indice guide indicizzato; homepage/HDR/trofei scansionati non indicizzati, patch/Moses/animali/taxi sconosciuti a Google nell'ultima verifica. Canonical e robots corretti per pagine note. OpenSEO/Search Console in lettura.
- Evidenze editoriali: fonti, decisioni, test e dettagli delle procedure sono nel codice, nelle PR e in ARTICLE-ROTATION-PLAN.md. Non duplicarli qui. Nessun gameplay o riproduzione video dichiarati verificati senza prova reale.

## Chiusura di ogni sessione
Fornire in chat un report breve: completato, verificato, da risolvere, massimo tre priorità. Aggiornare **questo stesso file su main** solo se cambia lo stato utile alla ripartenza, sostituendo le priorità concluse; mantenere circa 40 righe, senza aggiungere cronologia, credenziali o informazioni personali. Rileggere il file e usare il blob SHA attuale per evitare sovrascritture concorrenti. Non modificare configurazioni o avviare workflow solo per aggiornare la consegna. Il file è documentazione, non una configurazione eseguibile. I job autonomi continuano secondo la loro normale pianificazione.
