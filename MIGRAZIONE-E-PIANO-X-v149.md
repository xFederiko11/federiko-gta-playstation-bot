# GTA 6 Italia — Manutenzione e piano X v14.9

## Stato e proprietà editoriali

- Repository tecnica: `xFederiko11/federiko-gta-playstation-bot`, pubblicazione via Buffer esistente.
- Sito autorevole: `https://xfederiko11.github.io/gta-6/` con sezioni `/trofei/` e `/guide-e-tutorial/`.
- Vecchio GitHub Pages: usato **solo per 57 redirect HTML di compatibilità** (homepage, 55 vecchi URL e medaglie Oro), con `noindex,follow`, canonical sul sito nuovo e refresh. Questa migrazione non cancella il sito nuovo e non crea un'altra indicizzazione concorrente.
- Dati, registri, storico, file cifrati e metriche sono conservati. Il vecchio workflow Pages genera ancora `metrics.json`.

## Audit pubblicazione (18 novembre 2026)

La query read-only di Buffer eseguita da GitHub Actions ha restituito il messaggio esatto:
`Please reauthorize your channel connection.`

Il primo thread WAiNK è nel registro con stato `rejected`. Anche il primo tentativo del trofeo "Una lunga strada" è registrato come `rejected`. Una run GitHub verde **non** garantisce che il post sia su X. Non cancellare o modificare manualmente le voci con esito incerto.

### Sblocco sicuro

1. In Buffer: apri il canale **xFederiko11** e cerca l'avviso di connessione; seleziona **Reconnect/Reauthorize** e completa l'autorizzazione su X.
2. Controlla che la coda Buffer non sia in pausa e che il canale X sia quello corretto.
3. Verifica con un **nuovo thread di test in bozza**, con una foto ufficiale realmente accessibile, che Buffer consenta entrambi i messaggi con immagine solo nel primo. Non ritentare il post WAiNK già rifiutato.
4. Soltanto dopo un test riuscito e una verifica del canale, imposta la repository variable `TIPS_REAUTH_CONFIRMED_V149=true`. Il valore di default è `false`.
5. Il workflow editoriale già esistente selezionerà i successivi cinque tips con limite massimo di 2 al giorno e intervallo minimo di 110 minuti. Questa **non è** una prenotazione Buffer a orario fisso: i GitHub cron sono best-effort, il direttore editoriale controlla 22 minuti fra tentativi e le notizie importanti possono cambiare le priorità.
6. Il primo rifiuto resta nel ledger. **Se un altro quick tip fallisce**, la rubrica viene bloccata automaticamente anche con la variabile attiva.

## Calendario proposto (non ancora inserito nella coda Buffer)

Vedi `editorial-calendar-v149.json`. Tutti gli orari sono indicativi, fuso `Europe/Berlin`, e potranno slittare per breaking news, errori Buffer o verifiche editoriali.

| Data e ora CET | Tema | Link di destinazione |
| --- | --- | --- |
| 19/11 10:00 | Studiare 100 specie animali | `/guide-e-tutorial/studiare-animali/` |
| 19/11 14:00 | 70 sfide su 80 per il 100% | `/guide-e-tutorial/70-sfide-100-percento/` |
| 20/11 10:00 | Viaggio rapido in taxi | `/guide-e-tutorial/viaggio-rapido-taxi/` |
| 20/11 14:00 | Poligoni e medaglie Oro | `/guide-e-tutorial/poligoni-concentrazione/` |
| 21/11 10:00 | Meditazione Capitolo 1 | `/guide-e-tutorial/meditazione-capitolo-1/` |

L'ultimo tip richiede una verifica manuale del potenziale trofeo mancabile e degli spoiler prima del post.

## Formato X e norme

- Primo messaggio: emoji, intestazione `GTA VI`, due o tre passi in italiano, pulsanti PS5, vantaggio, massimo due hashtag pertinenti.
- Foto: ufficiale, pertinente, **illustrativa**, con diritto di riuso valutato caso per caso e senza ripetizioni inutili.
- Risposta al primo post: link diretto alla guida del sito, fonte PowerPyx e crediti sulle immagini.
- Mai considerare automaticamente ripubblicabili fotografie PowerPyx o di terzi.
- Limiti attuali: 2 quick tips per giorno UTC, 2 trofei al giorno UTC, cooldown di 110 minuti tra tips e 22 minuti tra workflow.
- Gli URL delle singole pagine vengono selezionati dal bot solo dopo una verifica HTTP 200 e canonical.

## Cleanup prudente

- Il vecchio Pages non deve continuare a generare copie indicizzabili dei 55 trofei.
- Mantieni il workflow di redirect e metriche fino a quando gli URL vecchi vengono usati da post su X e dai motori.
- Mantieni i workflow di campagna e launch watch durante la finestra del lancio; archiviali a fine periodo dopo audit finale.
- Non cancellare `.state/`, `history-public.*`, `metrics-manual-v142.csv`, `bootstrap-gta6-v3-state.json` o chiavi.
- I vecchi branch delle PR chiuse possono essere eliminati **solo dopo** un audit della loro storia. La connessione GitHub corrente non fornisce un'azione per cancellare branch.
- Nessun nuovo abbonamento.

## Verifica

Esegui `python -m unittest discover -q` e controlla i job di GitHub Actions. Dopo merge, avvia una sola build del vecchio Pages, conferma che i link `trofeo-14.html` redirigano al sito nuovo, e verifica `metrics.json` senza dati sensibili.
