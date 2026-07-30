/* Mounts the terminal recordings on the docs/why pages.
 *
 * Three branches, and the one that ships today is the placeholder: no cast has been
 * recorded yet, so every data-cast-id in docs/why/ is still empty.
 *
 * The asciinema.org branch builds the embed iframe here rather than injecting their
 * a/<id>.js. That script keys off its own <script id="asciicast-N"> element and
 * hardwires asciinema.org as the source; doing the only two things it adds over a bare
 * iframe ourselves (height from bodySize, textStyle on load and on scheme change) is
 * what lets one added data-cast-src move a figure onto a self-hosted player later
 * without touching this file.
 */

(() => {
  /* Also the postMessage target origin and the expected e.origin. Their script derives
   * it from its own src; we build the URL, so it is a constant. */
  const API_HOST = "https://asciinema.org";

  /* How long a frame may stay silent before it is called broken. Long, because the cost of
   * being wrong is asymmetric: a slow cast that reports late retracts the note itself. */
  const EMBED_DEADLINE_MS = 8000;

  /* Resolved from the live DOM on every broadcast instead of kept in a Set: instant
   * navigation discards the old nodes, and a Set would pin them for the session. Only
   * the asciinema.org branch puts an iframe inside a mount. */
  const embeds = () => document.querySelectorAll(".why-cast-mount > iframe");

  /* The embed styles its own surrounding text from what we send, so the values come
   * from the mount's computed style, not from constants — that is how it blends with
   * whichever palette the page is in. */
  function syncTextStyle(iframe) {
    if (!iframe.contentWindow) return; // detached mid page swap
    const style = window.getComputedStyle(iframe.parentElement);
    iframe.contentWindow.postMessage(
      {
        type: "textStyle",
        payload: {
          color: style.getPropertyValue("color"),
          fontFamily: style.getPropertyValue("font-family"),
          fontSize: style.getPropertyValue("font-size"),
        },
      },
      API_HOST,
    );
  }

  const syncAll = () => embeds().forEach(syncTextStyle);

  /* One window listener for the session, matching e.source against the mounts that are
   * currently in the document, where their script adds one listener per iframe. Same
   * origin + source guarantees, but nothing here outlives the node it sizes. */
  window.addEventListener("message", (e) => {
    if (e.origin !== API_HOST || e.data?.type !== "bodySize") return;
    for (const iframe of embeds()) {
      if (e.source !== iframe.contentWindow) continue;
      iframe.style.height = `${e.data.payload.height}px`;
      /* A reported height is the only proof the frame is really there, so it is also what
       * retracts a deadline note that a slow load already earned. */
      iframe.hidden = false;
      iframe.parentElement.querySelector(".why-cast-pending")?.remove();
    }
  });

  /* What their script listens to. */
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncAll);

  /* What it cannot: this theme's palette toggle sets body[data-md-color-scheme] and never
   * touches prefers-color-scheme, so the colour we forward would go stale on toggle.
   * The player's own terminal theme is fixed by the theme= query param and stays wrong
   * either way — that mismatch is the reason to self-host eventually, not a bug here.
   * body itself survives instant navigation; only its component subtrees are replaced. */
  new MutationObserver(syncAll).observe(document.body, { attributeFilter: ["data-md-color-scheme"] });

  function note() {
    /* One place for the class name, because why.css keys the pending box off it and both
     * the not-yet-recorded and the could-not-embed message are that same box. */
    const p = document.createElement("p");
    p.className = "why-cast-pending";
    return p;
  }

  function cmd(text) {
    const code = document.createElement("code");
    code.textContent = text;
    return code;
  }

  function failEmbed(el, iframe, id) {
    /* Idempotent, because the error event and the deadline both land here — and a height
     * that arrived in between means there was never anything wrong. */
    if (iframe.style.height || el.querySelector(".why-cast-pending")) return;
    iframe.hidden = true; // an unreported frame is 150px of blank; the note takes the space
    const p = note();
    p.append("Recording could not be embedded — watch it at ");
    const link = document.createElement("a");
    link.href = `${API_HOST}/a/${encodeURIComponent(id)}`;
    link.textContent = `asciinema.org/a/${id}`;
    p.appendChild(link);
    p.append(". If that link 404s, the id on this figure is stale and ");
    p.appendChild(cmd(`docs/casts/upload.sh ${el.dataset.castSlug || "<slug>"}`));
    p.append(" prints its replacement.");
    el.appendChild(p);
  }

  function mountEmbed(el, id, poster, label) {
    const iframe = document.createElement("iframe");
    /* Hand-assembled rather than URLSearchParams only to keep the pairs their script sends;
     * the encoding is not load-bearing, since the endpoint decodes poster=npt%3A0%3A02 to
     * the same npt:0:02. No preload pair: the /iframe bootstrap spreads the server-side opts
     * and then writes preload: true after them, so the param cannot reach the player —
     * asking for preload=0 yields opts with "preload":false and a call site still reading
     * preload: true. Their script only sends it when the author set data-preload anyway. */
    /* 1.5x by default: these are recordings of someone typing, and real typing is slower
     * than anyone wants to watch. Per-cast override is data-cast-speed, so tuning one
     * recording stays a markdown attribute rather than a change here. */
    const speed = el.dataset.castSpeed || "1.75";
    const query = `theme=asciinema&speed=${speed}${poster ? `&poster=${poster}` : ""}`;
    iframe.src = `${API_HOST}/a/${encodeURIComponent(id)}/iframe?${query}`;
    /* The authored description, on the element that actually holds the recording: a frame's
     * title is its accessible name, and the mount cannot carry one (see mount). */
    iframe.title = label || "Terminal session recording";
    iframe.scrolling = "no"; // the embed sizes itself; a scrollbar here is chrome twice
    iframe.setAttribute("allowfullscreen", "true");
    /* Hidden until the first textStyle lands, so the embed never paints in the other
     * palette's colours first. Height stays unset until bodySize arrives. */
    iframe.style.visibility = "hidden";
    iframe.addEventListener("load", () => {
      syncTextStyle(iframe);
      /* Their second pass, kept: the embed relays out after its font resolves, which is
       * after load. */
      window.setTimeout(() => syncTextStyle(iframe), 1000);
      iframe.style.visibility = "visible";
    });
    /* A wrong or deleted id gets a 404 that carries x-frame-options: SAMEORIGIN, where a
     * live cast sends no such header — so the browser refuses the frame, load still fires,
     * no bodySize ever arrives, and an iframe with no height is 150px of blank. A blocked or
     * offline frame never fires load and stays hidden: the same silence, no space taken.
     * Neither is visible to the success path, so the failure needs its own deadline; the
     * error event is that same handler for the cases a browser does report. */
    iframe.addEventListener("error", () => failEmbed(el, iframe, id));
    el.appendChild(iframe);
    /* Armed at mount rather than in the load handler, or the load-never-fires case would
     * never be checked. It holds el for the wait and no longer; an instant navigation in
     * between leaves it writing into a detached node, which paints nothing and is collected. */
    window.setTimeout(() => failEmbed(el, iframe, id), EMBED_DEADLINE_MS);
  }

  function mountSelfHosted(el, src, poster, label) {
    /* Unreachable until a player is vendored — window.AsciinemaPlayer is undefined today,
     * and the caller falls through rather than calling this. Deliberately unreachable
     * rather than absent: the switch off asciinema.org has to be one attribute. */
    const opts = { preload: true, fit: "width" };
    if (poster) opts.poster = poster;
    /* No frame to title here, so the description goes on the mount — but under role=group,
     * which takes a name without being children-presentational, so the player's own controls
     * stay in the accessibility tree instead of being pruned out of it. */
    if (label) {
      el.setAttribute("role", "group");
      el.setAttribute("aria-label", label);
    }
    window.AsciinemaPlayer.create(src, el, opts);
  }

  function mountPending(el) {
    const slug = el.dataset.castSlug;
    const p = note();
    p.append("Recording pending — ");
    p.appendChild(cmd(`docs/casts/rec.sh ${slug || "<slug>"}`));
    p.append(", then ");
    p.appendChild(cmd(`docs/casts/upload.sh ${slug || "<slug>"}`));
    p.append(", which prints the line to paste over this one.");
    if (!slug) p.append(" This figure has no data-cast-slug — see docs/casts/casts.txt for the ten.");
    el.appendChild(p);
  }

  function mount(el) {
    if (el.dataset.castMounted !== undefined) return;
    el.dataset.castMounted = "1"; // set first, so nothing can double-mount re-entrantly
    const { castSrc, castId, castPoster } = el.dataset;
    /* The authored role="img" + aria-label describe the recording, and both are wrong the
     * moment this div holds anything real: role="img" is children-presentational, so it
     * prunes the player's controls out of the accessibility tree while leaving them in the
     * tab order, and with the role gone aria-label is prohibited on a plain div. The mount
     * therefore always loses both, and each branch re-applies the description where it can
     * be read: on the frame's title, on a role=group, or nowhere at all — a recording that
     * does not exist yet has nothing to describe, and then the instruction is what gets
     * announced, which is the useful thing. */
    const label = el.getAttribute("aria-label");
    el.removeAttribute("role");
    el.removeAttribute("aria-label");
    /* src wins where both are set, or switching a recorded figure to the vendored player
     * would mean blanking its id too. A missing player is not an error, it is today. */
    if (castSrc && window.AsciinemaPlayer) {
      mountSelfHosted(el, castSrc, castPoster, label);
    } else if (castId) {
      mountEmbed(el, castId, castPoster, label);
    } else {
      mountPending(el);
    }
  }

  /* The only correct hook. navigation.instant replaces the content subtree in place, so
   * DOMContentLoaded fires once for the whole session and a <script> inside page content
   * is not reliably re-run; document$ re-emits after every swap. It is a ReplaySubject(1),
   * so subscribing late still gets the current document, and this file is loaded at
   * body-end — outside [data-md-component=container], the only subtree instant navigation
   * re-executes — so it runs once and the listeners above are attached once. */
  window.document$.subscribe(() => document.querySelectorAll(".why-cast-mount").forEach(mount));
})();
