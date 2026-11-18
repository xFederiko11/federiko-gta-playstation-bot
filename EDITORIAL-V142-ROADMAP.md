# GTA VI — Editorial Director v14.2: audit e roadmap

## 1. Qualità editoriale
Il filtro `editorial_director_v142.py` penalizza parodie, rumors, leak,
sponsorizzazioni, gossip e contenuti GTA-like non pertinenti. Dà precedenza
a Rockstar, PlayStation, PowerPyx, trofei, platino, PS5 Pro, patch, guide e
novità di gameplay. Il filtro non sostituisce la verifica del contenuto.

## 2. Coordinamento dei workflow
Il gruppo GitHub Actions `gta-v142-publication-global` serializza i run
dei quattro workflow di pubblicazione esistenti. Il director legge i registri
editoriale, gallerie, watch, trofei e monitor e applica **almeno 22 minuti**
di pausa fra tentativi di pubblicazione. Il monitor salva il proprio
timestamp prima della mutazione Buffer e pubblica al massimo un post per run.
La coda GitHub Actions può sostituire un run pending se molti eventi
arrivano insieme; i successivi schedule recuperano notizie ancora fresche.
Non sono garantite notifiche al minuto.

## 3. PowerPyx continuo
Restano quattro spotlight iniziali, ma `editorial-autopilot-v137-sources.json`
include anche l'RSS pubblico PowerPyx per nuove guide GTA VI. Se il feed
non risponde, il sistema lo segnala senza interrompere le altre testate.
Titoli verificati, tradotti in italiano, senza copiare le guide.

## 4. Stile e branding
Intestazione GTA VI, emoji pertinenti, uno o due paragrafi leggibili,
fonte esplicita e massimo due hashtag. L'account è indipendente:
nessuna falsa affiliazione con Rockstar o PlayStation.

## 5. Crescita misurabile
`growth_metrics_v142.py` aggrega i registri dei tentativi e degli esiti
Buffer in `_site/metrics.json`. I dati X reali (impression, like, risposte,
visite al profilo, nuovi follower) **non sono disponibili da Buffer** in
modo verificato e vanno importati manualmente da Analytics con
`metrics-manual-v142.csv`. Campi vuoti significano sconosciuti, non zero.
Il file CSV è nel repository pubblico: non inserirvi informazioni private.

## 6. Sicurezza e manutenzione
Le Actions restano bloccate a SHA immutabili, con permessi distinti.
Dependabot ha PR aperte e richiede revisione separata, soprattutto per
upgrade principali delle Actions e Playwright. Non effettuare merge al buio,
non cancellare lo storico o il journal anti-duplicati, non aggiungere
servizi a pagamento. Il monitor Rockstar Support ha segnalato ReadTimeout:
controllare errori successivi e backoff prima di modificare browser/reti.

## Prossimo controllo operativo
1. Verificare che la PR v14.2 superi tutti i test.
2. Controllare Pages in Settings e deploy della pagina HTML.
3. Confermare che il primo post della rubrica trofei riporti BUFFER_SENT.
4. Valutare dopo 48-72 ore quali rubriche portino clic e follower reali
   con i dati X disponibili, senza scambiare Buffer Sent per impression.
