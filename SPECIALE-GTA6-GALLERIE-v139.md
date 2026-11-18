# GTA VI — Speciale lancio v13.9

Data verifica editoriale: **18 novembre 2026**.

## Contenuti approvati

1. **GTA+ e GTA VI**: condizioni ufficiali [Rockstar](https://www.rockstargames.com/gta-plus/legal), vantaggi GTA+ destinati a GTA VI su PS5, e mese incluso per gli acquisti digitali in promozione, riscatto entro il 31/03/2027 secondo [PlayStation](https://www.playstation.com/en-us/support/games/gta-vi-offer-terms/). Gli abbonamenti si rinnovano a pagamento salvo disdetta.
2. **Vice City**: galleria di 4 screenshot ufficiali.
3. **Lucia Caminos**: galleria di 4 screenshot ufficiali (escluso il frame 01 già usato).
4. **Leonida Keys**: galleria di 4 screenshot ufficiali.

**Licenza e immagini:** solo asset direttamente referenziati dalla pagina Rockstar [Download and share](https://www.rockstargames.com/VI/media/screenshots). Sono contenuti copyright Rockstar; la disponibilità alla condivisione sul sito ufficiale non equivale al pubblico dominio. Nessuna immagine di fan, watermark rimossi, modifica o re-hosting. Ogni URL viene controllato prima di riservare un post; se inaccessibile, il post non parte. Alcuni provider possono rifiutare la sorgente nonostante i controlli; verificare la consegna Buffer.

**Nessuna ripetizione:** immagini distinte fra gallerie e confronto con `bootstrap-gta6-v3-state.json`, oltre al registro permanente `.state/special-campaign-v139.json`. Le gallerie non sono nuove immagini del giorno: sono raccolte tematiche da screenshot ufficiali pubblicati da Rockstar.

## Programmazione prudente

- **Post GTA+**: primo controllo disponibile dopo il deploy del workflow.
- **Vice City**: non prima delle 15:20 UTC del 18/11.
- **Lucia**: non prima delle 17:00 UTC del 18/11.
- **Leonida Keys**: non prima delle 19:00 UTC del 18/11.
- Mai più di **un post per run** e **35 minuti** dal precedente invio della campagna.
- Workflow programmato il 18-20 novembre e finestra applicativa conclusa alle **12:00 UTC del 20/11**.
- `AUTO_PUBLISH=true` richiesto per run schedulati; `workflow_dispatch=preview` è sempre senza pubblicazione.
- Prima della richiesta Buffer: riserva anti-duplicati registrata su GitHub. Dopo una richiesta incerta **nessun retry automatico**.
- La coda e gli altri workflow storici restano intatti.

## Repost ufficiali

`repost_v12.py` permette di comporre soltanto una **bozza** di retweet nativo Buffer a partire da un URL `https://x.com/RockstarGames/status/<id>` già verificato. I repost automatici **non sono attivati**: non usare come surrogato il copia-incolla di immagini o testo; finché non vengono verificati un URL ufficiale recente e una prova di consegna del retweet nativo, meglio condividere il link ufficiale come normale citazione correttamente etichettata, senza definirlo repost.

## Verifica

`python -m unittest -q test_gta6_special_campaign_v139 test_buffer_publisher`

Lo stato verde dell'Action non è prova di consegna: confermare `BUFFER_SENT` e la presenza del contenuto sulla scheda Sent di Buffer/X.
