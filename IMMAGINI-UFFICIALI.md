# Federiko News Center — Immagini ufficiali (v4)

## Regola di pubblicazione

- `official_images_only: true` in `sources.free.json` (gia' configurato).
- **Nessuna immagine creata dall'IA**. Le schede grafiche generate dal codice non vengono piu' usate per i post automatici.
- Un post singolo riceve l'immagine come `assets[0].image` tramite Buffer; un thread riceve l'immagine nel **primo tweet** (`metadata.twitter.thread[0].assets`). I successivi tweet nel thread riportano testo, fatti e fonte.
- Si accettano solo immagini derivate dalla **pagina ufficiale della specifica notizia** (tag `og:image` / `twitter:image` di Rockstar o PlayStation) e miniature dei video del canale YouTube ufficiale Rockstar.
- Si controllano dominio HTTPS, assenza di token temporanei, risposta del server, tipo di file e firma dell'immagine. Le immagini non vengono ritoccate, scaricate da raccolte di terze parti o sostituite da fotografie IA.
- Se non esiste un'immagine idonea, o il server ufficiale ne impedisce l'accesso, il record passa a `review` con `last_error=no_verified_official_image`; **non parte nessun post solo testuale**. Questa scelta puo' ridurre il numero di notizie pubblicate ma evita immagini fuorvianti.
- Crediti e contesto: ogni post singolo riporta il link alla fonte ufficiale; i thread lo riportano nel messaggio finale. Non presentare immagini d'archivio come screenshot della nuova patch.

## Fonti immagini

- Rockstar Newswire: https://www.rockstargames.com/newswire
- Media ufficiali GTA VI (download e condivisione di immagini): https://www.rockstargames.com/VI/media
- Note Sony PS5/PS4: https://www.playstation.com/it-it/support/hardware/ps5/system-software-info/
- Canale video Rockstar: https://www.youtube.com/channel/UC6VcWc1rAoWdBCM0JxrRQ3A

I diritti delle immagini restano ai rispettivi titolari. Non e' garantita una licenza generale per usi commerciali o modifiche; il bot usa URL pubblici ufficiali ed evidenzia sempre la fonte. Le immagini possono essere rimosse o bloccate dai fornitori.

## Limiti importanti

1. Buffer richiede una URL immagine pubblica, direttamente raggiungibile (https://developers.buffer.com/guides/hosting-media.html). Un sito ufficiale potrebbe limitare l'hotlink o sostituire un contenuto: nel dubbio niente invio automatico.
2. L'immagine recuperata da una pagina ufficiale non e' sempre la piu' spettacolare; **la scelta di una gallery editoriale ricorrente e di overlay grafici non e' implementata**. Le immagini generiche, le icone e i loghi vengono scartati quando riconoscibili dall'URL.
3. Nessuna pubblicazione reale X e' stata eseguita per verificare la nuova funzionalita'. Test locali verificano la costruzione dell'input Buffer, non la consegna effettiva.
4. `AUTO_PUBLISH` deve rimanere `false` fino al controllo di un nuovo `check` e alla verifica delle fonti. Per la transizione dalla v2 l'aggiornamento include `online.py` della v3, che sopprime le bozze accumulate in precedenza senza eliminare lo storico.

## Passaggi d'installazione

Caricare insieme nella root del repository tutti i file del pacchetto v4 (eccetto questo file, che si puo' caricare anch'esso come documentazione), lasciando invariato `.github/workflows/gta-monitor.yml`, i Secrets e `AUTO_PUBLISH=false`. Avviare Actions → GTA Monitor gratuito → Run workflow → `check` e cercare nei log `FOTO UFFICIALE VERIFICATA` oppure `FOTO UFFICIALE NON DISPONIBILE`.
