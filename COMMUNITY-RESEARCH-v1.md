# GTA VI — fonti specialistiche e community (ricerca editoriale)

Aggiornato: 19 novembre 2026. Questa pagina definisce come le fonti indipendenti supportano articoli, tutorial e novità senza essere scambiate per comunicazioni di Rockstar.

## Gerarchia di affidabilità

| Tipo | Esempi | Utilizzo corretto |
|---|---|---|
| Ufficiali | Rockstar Games, PlayStation e relativi supporti | Conferme su patch, date, SKU, distribuzione e dichiarazioni |
| Guide indipendenti | PowerPyx, GTA Series Videos | Tutorial, walkthrough, checklist, codici e video da confrontare con gioco e patch |
| Database | GTABase, GTANet | Veicoli, luoghi, modelli, meccaniche e link alla fonte primaria |
| Community / wiki | GTAForums, GTA Wiki/Fandom | Segnalazioni e confronti. Possibili spoiler, voci e dati non aggiornati |
| Dataminer | Tez2 (TezFunz2) | Piste basate su file: non dichiarare «Rockstar ha annunciato» |
| Giornalisti | Jason Schreier / Bloomberg | Inchieste e scoop attribuiti: non equivalgono a comunicati ufficiali |

La credibilità personale di una fonte non trasforma una notizia in una conferma ufficiale. Fonti che riprendono il medesimo articolo o video non contano come riscontri indipendenti.

## Cosa è davvero automatizzato

- PowerPyx: feed di guide **già attivo** nell'Editorial Autopilot, con regole di deduplicazione e attribuzione.
- GTA Series Videos: RSS/Atom YouTube via ID canale pubblico, raccolto dal nuovo **ricercatore in sola lettura**. I titoli dei video possono entrare separatamente nell'Editorial Autopilot solo dopo le stesse regole di traduzione, antirumor, dedupe e attribuzione come contenuti di un creator indipendente; non copia video o screenshot.
- GTAForums, GTA Wiki/Fandom, GTABase, GTANet, Tez2, Jason Schreier: elenco consultabile in \`community-research-sources-v1.json\` come fonti di ricerca/verifica. Nessuna acquisizione automatica finché non è stato individuato e autorizzato un feed affidabile. GTAForums può rifiutare l'accesso automatizzato; non aggiriamo la protezione.
- Rockstar: **resta nel monitor ufficiale esistente**, non viene duplicato nel ricercatore.

### Workflow

\`.github/workflows/gta6-community-research-v1.yml\` controlla i due feed pubblici alle 07:17, 13:17 e 19:17 UTC e tramite avvio manuale.

Il workflow di ricerca ha permesso di lettura del repository e permesso limitato `issues:write` per aggiornare una sola Issue editoriale. **Non riceve credenziali Buffer e non può pubblicare su X**. Esegue test offline, filtra argomenti pertinenti e titoli rumorosi, limita le fonti agli host esplicitamente autorizzati, e deposita il file \`gta6-community-research\` come artifact per sette giorni.

Il digest contiene **piste** per articoli; non è una pubblicazione e non dimostra che tutti gli articoli proposti siano confermati. Ogni elemento segnala titolo, URL originale, data, tipo e fonte. I nuovi feed si aggiungono solo con dominio, permesso e prova di accessibilità validati.

## Da pista ad articolo originale

1. Apri il link originale e verifica data, provenienza, titolo, video/screenshot e versione del gioco. Non riutilizzare media terzi senza diritti.
2. Segnala distintamente: **ufficiale**, **riportato da testata**, **community/testimonianza**, **rumor**, **storico/patched**. I post di Tez2 e le notizie Bloomberg vanno attribuiti.
3. Per **trucchi** confronta esattamente sequenza dei tasti, modalità di inserimento, PS5, patch, requisiti e impatto su trofei e salvataggi. Un codice controverso resta «incerto» o viene temporaneamente escluso.
4. Per **glitch** richiedi almeno due riscontri indipendenti dopo l'ultima patch, indicando il rischio trofei; se incerto, non presentarlo come migliore metodo per il platino.
5. Per **notizie** prediligi testo editoriale italiano originale che aggiunge contesto, confronto, procedure e fonte. Niente parafrasi integrali o riproduzioni automatiche da forum/wiki. Conserva un link diretto all'originale e dati SEO veritieri (canonical, data di aggiornamento reale e metadati).

**Se una fonte non è accessibile o offre soltanto un indice obsoleto, non affermare di averne letto gli aggiornamenti.** Conserva il link e registra il limite.

## Fonti principali

- https://www.powerpyx.com/gta-6-all-cheats/
- https://gtaforums.com/
- https://gta.fandom.com/wiki/Grand_Theft_Auto_VI
- https://gta.wiki/
- https://gtaseries.com/
- https://www.youtube.com/@GTASeriesVideos
- https://www.gtabase.com/
- https://www.gtanet.com/
- https://x.com/TezFunz2
- https://www.bloomberg.com/authors/AUyIKVhIKU8/jason-schreier

La pagina è una policy operativa: **non promette** che ogni sito fornisca feed, API, o nuovi contenuti disponibili oggi.

## Autonomia del monitor (v1)

Il workflow GitHub Actions esegue la scansione tre volte al giorno indipendentemente da ChatGPT. Un job con soli permessi di lettura acquisisce i feed pubblici e produce un artifact JSON e un riepilogo. Un secondo job (solo ramo `main`) può creare/aggiornare una **sola GitHub Issue** chiamata `GTA VI - Coda fonti community`, con etichette `GUIDA INDIPENDENTE`, `COMMUNITY`, `DATAMINING` e `RUMOR` e indicazioni su errori feed. Un fallimento fa fallire il workflow invece di passare inosservato. Il bot Buffer conserva il proprio filtro più restrittivo: l'inserimento nella coda NON equivale a pubblicazione su X o sul sito, né a conferma della notizia.

Il ricercatore conserva i rumor nei risultati *soltanto* per poterli segnalare come non verificati. Non elude protezioni di GTAForums o Fandom; queste fonti restano di consultazione manuale fino a validazione di un feed pubblico. Non possiamo garantire disponibilità eterna di GitHub Actions, RSS, Buffer o servizi esterni: manutenzione e controllo credenziali rimangono necessari.
