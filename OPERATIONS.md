# GTA VI News Center — operations

This is a public production repository. It posts to X through existing Buffer credentials and runs on standard GitHub-hosted runners.

## Configurazione editoriale corrente — dal 23 novembre 2026

- **Frequenza X approvata:** obiettivo **5–6 post originali utili al giorno** dalle **07:00 alle 23:00 Europe/Rome**, con massimo **6 post ordinari per finestra mobile di 24 ore**, distanza minima di **120 minuti** e limite autonomo di **12 messaggi X** (un thread di due messaggi conta come un post ma due messaggi). L'obiettivo non autorizza post riempitivi.
- **Notizie urgenti:** fino a 2 ulteriori pubblicazioni nelle 24 ore, distanziate almeno 30 minuti, soltanto con classificazione e URL ufficiale verificati. Mai rispondere automaticamente a utenti terzi.
- **Codice di riferimento:** `quality_publish_policy_v1.py`, `editorial_director_v142.py`; l'applicazione del controllo dipende dalla variabile `EDITORIAL_DIRECTOR_V142_ENABLED` impostata nei workflow di produzione. Verificare sempre ricevute Buffer Sent e permalink X: prenotazioni e workflow verdi non dimostrano una pubblicazione.
- **Campagna precedente terminata:** l'obiettivo di 10–16 thread al giorno apparteneva esclusivamente alla finestra 19–22 novembre 2026 definita in `launch_cadence_v1.py`; non è più la politica attiva.

## Audit storico — 21 novembre 2026 (non usare come configurazione attuale)

- **Sito GTA VI Italia:** [GitHub Pages](https://xfederiko11.github.io/gta-6/) e Search Console collegati. Homepage e /guide-e-tutorial/ risultano *indicizzate* dalla URL Inspection OpenSEO; /trofei/ e /hdr-oled/ scansionate ma non ancora indicizzate, /soldi-facili/ ancora sconosciuta. Nessuna impression/clic disponibili nel campione GSC 12–18 novembre. La verifica futura è gestita da un'automazione dedicata, non da questo repository.
- **Umami:** script pubblico configurato e visita reale osservata in screenshot proprietario. I futuri link alle guide in risposte a thread propri di @xFederiko11 includono UTM per classificare la sorgente; **non** abbiamo prove di follower acquisiti né di eventi `x-follow-intent` già ricevuti.
- **Campagna X (nota storica):** il piano originario prevedeva 10–16 thread al giorno fino al 2 dicembre, ma il codice lo ha **sostituito dal 23 novembre** con la politica 5–6 post/die indicata sopra. Non utilizzare questa voce per configurare la produzione.
- **Buffer:** il campione dell'[audit #50](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/50) del 20 novembre riportava 15 Sent, 0 Scheduled e 0 Error nel campione di massimo 15 per stato, con 10 slot editoriali verificati per *primo post*. Non certifica tutte le pubblicazioni né le risposte numero due dei thread; l'ultimo record con permalink verificato è 20/11 ore 19:34Z. La diagnosi di staleness avvisa soltanto se ci sono tentativi recenti irrisolti insieme a ricevute Sent più vecchie di 24 ore; mai ripetere una mutazione ambigua.
- **Reddit:** 12 lead ricevuti via IFTTT/GitHub e dashboard automatica [#68](https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/68). Priorità di **revisione** P1 glitch PS5, P2 trofei/soldi/auto, P3 foto/guide, P4 domande ambigue. Da titoli e permalink non possiamo concludere che un glitch funzioni o che una foto sia autorizzata.
- **Sito fotografico:** [hub screenshot PS5](https://xfederiko11.github.io/gta-6/screenshot-ps5/) con 55 richieste e 11 guide, al momento **0/11** al target di cinque screenshot operativi unici. Le copertine promozionali non contano e ogni eventuale riuso richiede diritti confermati.
- **X Social Radar:** scanner gratuito parziale e ricerca X API completa **disattivata** per evitare spese non autorizzate. Niente commenti o like automatici.
- **Dominio:** mantenere l'attuale URL GitHub Pages gratuito mentre Google inizia a indicizzare. La migrazione verso un dominio personale richiederebbe dominio posseduto, reindirizzamenti e monitoraggio SEO; non cambiare URL per motivi puramente estetici nel periodo di lancio.

Le statistiche riportano *fonti, perimetri e limiti diversi*. Non sommare Sent del registro con Sent della coda, né visite e click Umami con follower X.

## Active workflows

- GTA Monitor gratuito: Rockstar, PlayStation and verified YouTube links.
- Breaking News Watch v13.4: official breaking news.
- Editorial Autopilot v13.7: press articles plus four curated PowerPyx launch spotlights.
- Special Campaign v13.9: short-lived official Rockstar image campaign, expiring 20 November 2026.

Keep workflow names stable: some automations depend on their names. Do not delete the .state directory, archived launch ledgers, bootstrap-gta6-v3-state.json or history-public.json.

## PowerPyx editorial coverage

Four original Italian posts from PowerPyx guides dated 18 November 2026: platinum roadmap, 70/80 challenges, missions/manual saves, and collectible database. Each carries an official link to the corresponding PowerPyx article. Spotlight window ends 24 November 2026 UTC; at least 120 minutes separate them. The existing editorial ledger controls deduplication. New posts must remain source-verified; PowerPyx estimates are attributed, not official Rockstar statements.

## X engagement

No new subscriptions. Buffer API does not provide the required X reply-reading/posting workflow for automatic public comment outreach. See OUTREACH-X-PLAYBOOK.md for manual draft responses to verified relevant videos; do not claim that comments were posted.

## Verify that a post was published

Check the GitHub run event, then the reserve step, then BUFFER_SENT (or BUFFER_PENDING). A green run with RESERVE count=0 or DELIVERY_NOT_ATTEMPTED means no new post. Confirm the post in Buffer Sent and on X where possible. Do not repeat uncertain deliveries: Buffer may have received the original mutation.

## Maintenance

Review logs and quotas weekly. Apply dependency updates only after tests and review. Keep GitHub Secrets private and prefer least-privilege workflow permissions. The previous Buffer Essentials through-date in workflow configuration is 15 December 2026; verify the plan before that date. No extra paid service is permitted.
