# Immagini autentiche e logo ufficiale - priorita v5

Il News Center non genera immagini con IA, non usa foto di community e non scarica
immagini casuali tramite motori di ricerca. `official_images_only: true` resta
impostato in `sources.free.json`.

## Ordine obbligatorio (il logo e l'ultima opzione)

1. Foto/artwork originale allegato dall'evento ufficiale, dal dominio consentito.
2. Foto ufficiale indicata dai metadati `og:image` / `twitter:image` della
   **specifica pagina** Rockstar o PlayStation.
3. Foto incorporata nel corpo `<article>` ufficiale, escludendo loghi, icone,
   pubblicita e miniature dei menu. Per i video del canale YouTube Rockstar
   verificato, si usa la miniatura originale del video.
4. **Solo se le opzioni precedenti falliscono**: un logo autentico e appropriato,
   verificato dal server prima dell'invio:
   - notizia **GTA VI**: logo GTA VI da una pagina Newswire Rockstar;
   - notizia **PlayStation/PS5/PS4**: logo PlayStation dal PlayStation Blog;
   - altre notizie Rockstar, es. GTA Online, **non** ricevono il logo GTA VI.
5. Se manca anche il logo verificato: stato `review`, nessun invio.

Le due risorse per il fallback sono identificativi URL approvati singolarmente,
non un permesso generale di usare qualsiasi file con `logo` nel nome.

- GTA VI: https://www.rockstargames.com/newswire/article/3928aaa9471o3a/grand-theft-auto-vi-watch-trailer-2-now
- PlayStation: https://blog.playstation.com/2026/0/

## Controlli di sicurezza

- Fonte evento ufficiale; immagine e logo dai domini di riferimento corretti.
- Solo HTTPS, senza token in URL, niente redirect verso host esterni.
- Contenuto effettivo JPEG/PNG/WebP, dimensione dichiarata limitata.
- Niente loghi fasulli o di piattaforme sbagliate.
- L'esito `check` distingue `IMMAGINE UFFICIALE` da `LOGO UFFICIALE (ultima opzione)`.
- Buffer usa il link pubblico dell'immagine per i post e il primo elemento dei
  thread. La verifica HTTP del runner **non garantisce** che i server di Buffer
  possano scaricare il file: fare un test API in bozza prima di attivare l'invio.

## Fonte e marchi

Le immagini sono pubblicate da Sony e Rockstar. Il News Center resta un progetto
editoriale indipendente: la presenza di loghi non significa che l'account sia
ufficiale o affiliato ai titolari dei marchi. Rispettare sempre le condizioni
applicabili alla condivisione dei contenuti ufficiali.

La variabile `AUTO_PUBLISH` deve rimanere `false` sino alla conclusione del test
Buffer e alla validazione dello storico del bot.
