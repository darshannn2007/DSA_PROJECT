/**
 * CampusHive Frontend Application
 * Pure vanilla ES6+ JavaScript — Safe DOM rendering (textContent only for user data).
 */
(() => {
  "use strict";

  /* ========================================================================
     1. Application State
     ======================================================================== */
  const AppState = {
    currentUser: null,
    feedCursor: null,
    feedLoading: false,
    searchAbortController: null,
    mySkills: [],
  };

  const PUBLIC_PAGES = new Set(["landing", "login", "register", "help", "terms", "privacy"]);
  const AUTH_ONLY_PAGES = new Set(["login", "register"]);

  function validatePasswordPolicyClient(password) {
    if (password.length < 8 || password.length > 128) {
      return "Password must be between 8 and 128 characters.";
    }
    if (/\s/.test(password)) {
      return "Password must not contain spaces.";
    }
    if (!/[A-Z]/.test(password)) {
      return "Password must contain at least 1 uppercase letter.";
    }
    if (!/[a-z]/.test(password)) {
      return "Password must contain at least 1 lowercase letter.";
    }
    if (!/[0-9]/.test(password)) {
      return "Password must contain at least 1 digit.";
    }
    if (!/[^a-zA-Z0-9\s]/.test(password)) {
      return "Password must contain at least 1 special character.";
    }
    return null;
  }

  function syncYearOptionsForDegree(level, selectedYear = null) {
    const yearInput = document.getElementById("year");
    if (!yearInput) return;
    const maxYear = level === "PG" ? 2 : 4;
    const currentVal = selectedYear || Number.parseInt(yearInput.value, 10) || 1;
    clearElement(yearInput);
    for (let y = 1; y <= maxYear; y += 1) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = `Year ${y}`;
      yearInput.appendChild(opt);
    }
    yearInput.value = String(Math.min(Math.max(currentVal, 1), maxYear));
  }

  function getCookie(name) {
    const prefix = `${name}=`;
    const parts = document.cookie.split(";");
    for (const part of parts) {
      const trimmed = part.trim();
      if (trimmed.startsWith(prefix)) {
        return decodeURIComponent(trimmed.slice(prefix.length));
      }
    }
    return "";
  }

  /* ========================================================================
     2. Core API & Utility Helpers
     ======================================================================== */

  /**
   * Perform a JSON API request using fetch with same-origin credentials.
   * @param {string} method - HTTP verb (GET, POST, PATCH, DELETE)
   * @param {string} url - API endpoint path
   * @param {object|null} [body=null] - Optional JSON payload
   * @param {object} [options={}] - Optional fetch options (e.g. signal)
   * @returns {Promise<any>} Parsed response JSON or null for 204
   */
  async function api(method, url, body = null, options = {}) {
    const upperMethod = method.toUpperCase();
    const headers = {
      Accept: "application/json",
      ...(options.headers || {}),
    };
    if (["POST", "PUT", "PATCH", "DELETE"].includes(upperMethod)) {
      const csrf = getCookie("csrf_token");
      if (csrf) headers["X-CSRF-Token"] = csrf;
    }

    const fetchOptions = {
      method: upperMethod,
      credentials: "same-origin",
      ...options,
      headers,
    };

    if (body !== null && body !== undefined) {
      fetchOptions.headers["Content-Type"] = "application/json";
      fetchOptions.body = JSON.stringify(body);
    }

    const response = await fetch(url, fetchOptions);

    if (response.status === 204) {
      return null;
    }

    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        data = await response.json();
      } catch (_) {
        data = null;
      }
    } else {
      const text = await response.text();
      data = text ? { message: text } : null;
    }

    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      if (data) {
        if (typeof data.message === "string" && data.message) {
          message = data.message;
        } else if (typeof data.detail === "string" && data.detail) {
          message = data.detail;
        } else if (Array.isArray(data.detail) && data.detail.length > 0) {
          message = data.detail.map((item) => item.msg || String(item)).join("; ");
        }
      }
      const err = new Error(message);
      err.status = response.status;
      err.code = data?.code || null;
      err.data = data;
      throw err;
    }

    return data;
  }

  /**
   * Format an ISO timestamp into a human-friendly relative string.
   * @param {string|Date} isoDate
   * @returns {string}
   */
  function formatRelativeTime(isoDate) {
    if (!isoDate) return "";
    let date;
    if (isoDate instanceof Date) {
      date = isoDate;
    } else if (typeof isoDate === "string") {
      const trimmed = isoDate.trim();
      const hasTz = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
      date = new Date(hasTz ? trimmed : `${trimmed}Z`);
    } else {
      date = new Date(isoDate);
    }
    if (Number.isNaN(date.getTime())) return "";

    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 10) return "just now";
    if (seconds < 60) return `${seconds}s ago`;

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;

    const weeks = Math.floor(days / 7);
    if (weeks < 4) return `${weeks}w ago`;

    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: date.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
    });
  }

  /**
   * Compute 1-2 uppercase initials from a display name or username.
   * @param {string} name
   * @returns {string}
   */
  function getInitials(name) {
    if (!name || typeof name !== "string") return "?";
    const cleaned = name.trim();
    if (!cleaned) return "?";
    const parts = cleaned.split(/[\s_.-]+/).filter(Boolean);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return cleaned.slice(0, 2).toUpperCase();
  }

  /**
   * Show a dismissible toast notification in #toast-container.
   * @param {string} message
   * @param {"info"|"success"|"error"|"warning"} [type="info"]
   * @param {number} [duration=4000]
   */
  function showToast(message, type = "info", duration = 4000) {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.setAttribute("role", "status");

    const textEl = document.createElement("span");
    textEl.textContent = message;

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "toast-close";
    closeBtn.setAttribute("aria-label", "Dismiss notification");
    closeBtn.textContent = "×";

    const dismiss = () => {
      toast.classList.add("is-leaving");
      setTimeout(() => toast.remove(), 180);
    };

    closeBtn.addEventListener("click", dismiss);
    toast.append(textEl, closeBtn);
    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(dismiss, duration);
    }
  }

  /**
   * Create a debounced wrapper around a function.
   * @param {Function} fn
   * @param {number} delayMs
   * @returns {Function}
   */
  function debounce(fn, delayMs = 300) {
    let timerId = null;
    return (...args) => {
      if (timerId !== null) clearTimeout(timerId);
      timerId = setTimeout(() => {
        timerId = null;
        fn(...args);
      }, delayMs);
    };
  }

  /**
   * Determine the current page identifier from body[data-page] or URL path.
   * @returns {string}
   */
  function getCurrentPage() {
    const attr = document.body?.dataset?.page;
    if (attr) return attr;
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    if (path === "/") return "landing";
    if (path.endsWith("/login")) return "login";
    if (path.endsWith("/register")) return "register";
    if (path.endsWith("/home")) return "home";
    if (path.endsWith("/my-profile") || path.endsWith("/me")) return "my_profile";
    if (path.includes("/profile") || path.includes("/users/")) return "profile";
    if (path.endsWith("/connections")) return "connections";
    if (path.endsWith("/requests")) return "requests";
    if (path.endsWith("/discover")) return "discover";
    if (path.endsWith("/groups")) return "groups";
    if (path.endsWith("/settings")) return "settings";
    if (path.endsWith("/help")) return "help";
    if (path.endsWith("/terms")) return "terms";
    if (path.endsWith("/privacy")) return "privacy";
    if (path.endsWith("/search")) return "search";
    if (path.endsWith("/notifications")) return "notifications";
    return "landing";
  }

  /**
   * Build a clean profile URL for a given username.
   * @param {string} username
   * @returns {string}
   */
  function profileUrl(username) {
    return `/profile?username=${encodeURIComponent(username)}`;
  }

  /**
   * Safely clear all children of a DOM container.
   * @param {HTMLElement} el
   */
  function clearElement(el) {
    while (el && el.firstChild) {
      el.removeChild(el.firstChild);
    }
  }

  /**
   * Render a centered loading spinner inside a container.
   * @param {HTMLElement} container
   * @param {string} [label="Loading..."]
   */
  function renderLoading(container, label = "Loading...") {
    if (!container) return;
    clearElement(container);
    const wrapper = document.createElement("div");
    wrapper.className = "spinner-wrapper";
    const spinner = document.createElement("div");
    spinner.className = "spinner";
    spinner.setAttribute("aria-hidden", "true");
    const text = document.createElement("span");
    text.textContent = label;
    wrapper.append(spinner, text);
    container.appendChild(wrapper);
  }

  /**
   * Render a friendly empty-state card inside a container.
   * @param {HTMLElement} container
   * @param {string} title
   * @param {string} description
   * @param {string} [icon=""]
   * @param {{label: string, href: string}|null} [cta=null]
   */
  function renderEmptyState(container, title, description, icon = "", cta = null) {
    if (!container) return;
    clearElement(container);
    const box = document.createElement("div");
    box.className = "empty-state";

    const titleEl = document.createElement("h2");
    titleEl.className = "empty-state-title";
    titleEl.textContent = title;

    const descEl = document.createElement("p");
    descEl.className = "empty-state-desc";
    descEl.textContent = description;

    box.append(titleEl, descEl);

    if (cta && cta.href && cta.label) {
      const link = document.createElement("a");
      link.href = cta.href;
      link.className = "btn btn-primary btn-sm";
      link.textContent = cta.label;
      box.appendChild(link);
    }

    container.appendChild(box);
  }

  /**
   * Create a reusable initials avatar element.
   * @param {string} name
   * @param {string} [sizeClass=""]
   * @returns {HTMLDivElement}
   */
  function createAvatar(name, sizeClass = "") {
    const avatar = document.createElement("div");
    avatar.className = sizeClass ? `avatar ${sizeClass}` : "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = getInitials(name);
    return avatar;
  }

  /* ========================================================================
     3. Theme Management (Dark / Light Mode)
     ======================================================================== */
  function initTheme() {
    const saved = localStorage.getItem("cc-theme");
    if (saved === "dark" || saved === "light") {
      document.documentElement.setAttribute("data-theme", saved);
    }

    const toggleBtn = document.getElementById("theme-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const currentAttr = document.documentElement.getAttribute("data-theme");
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        const isCurrentlyDark = currentAttr === "dark" || (!currentAttr && prefersDark);
        const next = isCurrentlyDark ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("cc-theme", next);
      });
    }
  }

  /* ========================================================================
     4. Authentication & Navigation
     ======================================================================== */

  /**
   * Verify session status via GET /api/v1/auth/me and enforce page redirects.
   * @param {string} page
   * @returns {Promise<object|null>}
   */
  async function checkAuth(page) {
    try {
      const user = await api("GET", "/api/v1/auth/me");
      AppState.currentUser = user;
      if (AUTH_ONLY_PAGES.has(page)) {
        window.location.replace("/home");
        return user;
      }
      return user;
    } catch (err) {
      AppState.currentUser = null;
      if (!PUBLIC_PAGES.has(page)) {
        window.location.replace("/login");
      }
      return null;
    }
  }

  /**
   * Populate navbar username, active link highlight, mobile toggle, and logout.
   */
  function setupNav() {
    const navToggle = document.getElementById("nav-toggle");
    const navMenu = document.getElementById("nav-menu");
    if (navToggle && navMenu) {
      navToggle.addEventListener("click", () => {
        const isOpen = navMenu.classList.toggle("is-open");
        navToggle.setAttribute("aria-expanded", String(isOpen));
      });
    }

    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", async () => {
        logoutBtn.disabled = true;
        try {
          await api("POST", "/api/v1/auth/logout");
        } catch (_) {
          // Proceed to login even if session already expired
        }
        AppState.currentUser = null;
        window.location.replace("/login");
      });
    }

    // Me dropdown toggle
    const meBtn = document.getElementById("me-menu-btn");
    const meMenu = document.getElementById("me-dropdown-menu");
    if (meBtn && meMenu) {
      meBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isHidden = meMenu.classList.toggle("hidden");
        meBtn.setAttribute("aria-expanded", String(!isHidden));
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".me-dropdown-wrap")) {
          meMenu.classList.add("hidden");
          meBtn.setAttribute("aria-expanded", "false");
        }
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          meMenu.classList.add("hidden");
          meBtn.setAttribute("aria-expanded", "false");
        }
      });
    }

    // Inline navbar search redirects to merged Discover & Search page
    const navSearchForm = document.getElementById("nav-search-form");
    const navSearchInput = document.getElementById("nav-search-input");
    if (navSearchForm && navSearchInput) {
      navSearchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const q = navSearchInput.value.trim();
        window.location.href = q ? `/search?q=${encodeURIComponent(q)}` : "/search";
      });
    }
  }

  /**
   * Update navbar user display and unread notifications badge.
   * @param {object|null} user
   */
  function updateNavBar(user) {
    const usernameEl = document.getElementById("nav-username");
    if (usernameEl && user) {
      usernameEl.textContent = user.username;
    }
    const meName = document.getElementById("me-menu-name");
    const meSub = document.getElementById("me-menu-sub");
    const meProf = document.getElementById("me-menu-profile");
    if (user) {
      if (meName) meName.textContent = `@${user.username}`;
      if (meSub) meSub.textContent = user.email || "CampusHive Student";
      if (meProf) meProf.href = profileUrl(user.username);
    }
  }

  /**
   * Fetch unread notification count and update #nav-notif-badge.
   */
  async function updateNotificationBadge() {
    const badge = document.getElementById("nav-notif-badge");
    if (!badge || !AppState.currentUser) return;
    try {
      const data = await api("GET", "/api/v1/notifications");
      const count = typeof data?.unread_count === "number"
        ? data.unread_count
        : (data?.notifications || []).filter((n) => !n.read_at).length;

      if (count > 0) {
        badge.textContent = count > 99 ? "99+" : String(count);
        badge.classList.remove("is-zero");
      } else {
        badge.textContent = "";
        badge.classList.add("is-zero");
      }
    } catch (_) {
      // Silently ignore badge refresh failures
    }
  }

  /* ========================================================================
     5. Auth Pages (Login & Register)
     ======================================================================== */
  function initLoginPage() {
    const form = document.getElementById("login-form");
    const errorBox = document.getElementById("login-error");
    const usernameInput = document.getElementById("login-username");
    const passwordInput = document.getElementById("login-password");
    const submitBtn = document.getElementById("login-submit");

    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errorBox.textContent = "";

      const username = usernameInput.value.trim();
      const password = passwordInput.value;

      if (!username || !password) {
        errorBox.textContent = "Please enter both your username and password.";
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Signing in...";

      try {
        await api("POST", "/api/v1/auth/login", { username, password });
        showToast("Signed in successfully!", "success", 2000);
        window.location.replace("/home");
      } catch (err) {
        errorBox.textContent = err.message || "Invalid username or password.";
        submitBtn.disabled = false;
        submitBtn.textContent = "Sign In";
      }
    });
  }

  function initRegisterPage() {
    const form = document.getElementById("register-form");
    const errorBox = document.getElementById("register-error");
    const usernameInput = document.getElementById("register-username");
    const emailInput = document.getElementById("register-email");
    const passwordInput = document.getElementById("register-password");
    const confirmInput = document.getElementById("register-confirm");
    const submitBtn = document.getElementById("register-submit");

    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errorBox.textContent = "";

      const username = usernameInput.value.trim();
      const email = emailInput.value.trim() || null;
      const password = passwordInput.value;
      const confirm = confirmInput.value;

      if (username.length < 3 || username.length > 30) {
        errorBox.textContent = "Username must be between 3 and 30 characters.";
        return;
      }
      if (!/^[a-zA-Z0-9_]+$/.test(username)) {
        errorBox.textContent = "Username can only contain letters, numbers, and underscores.";
        return;
      }
      const pwErr = validatePasswordPolicyClient(password);
      if (pwErr) {
        errorBox.textContent = pwErr;
        return;
      }
      if (password !== confirm) {
        errorBox.textContent = "Passwords do not match.";
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Creating account...";

      try {
        await api("POST", "/api/v1/auth/register", { username, email, password });
        showToast("Account created! Welcome to CampusHive.", "success", 2500);
        window.location.replace("/home");
      } catch (err) {
        errorBox.textContent = err.message || "Could not create account.";
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Account";
      }
    });
  }

  /* ========================================================================
     6. Home Feed & Post Composer
     ======================================================================== */

  /**
   * Build a safe DOM post card element from a PostResponse object.
   * @param {object} post
   * @returns {HTMLElement}
   */
  function createPostCard(post) {
    const card = document.createElement("article");
    card.className = "card post-card";
    card.dataset.postId = String(post.id);

    const author = post.author || {};
    const displayName = author.display_name || author.username || "Student";
    const username = author.username || "unknown";

    const header = document.createElement("div");
    header.className = "post-header";

    const authorGroup = document.createElement("div");
    authorGroup.className = "post-author-group";

    const avatar = createAvatar(displayName);

    const meta = document.createElement("div");
    meta.className = "post-author-meta";

    const nameLink = document.createElement("a");
    nameLink.href = profileUrl(username);
    nameLink.className = "post-author-name";
    nameLink.textContent = displayName;

    const sub = document.createElement("div");
    sub.className = "post-author-sub";
    const subParts = [`@${username}`];
    if (author.programme) subParts.push(author.programme);
    if (author.year) subParts.push(`Year ${author.year}`);
    sub.textContent = subParts.join(" · ");

    meta.append(nameLink, sub);
    authorGroup.append(avatar, meta);

    const timeEl = document.createElement("time");
    timeEl.className = "post-time";
    if (post.created_at) {
      timeEl.dateTime = post.created_at;
    }
    timeEl.textContent = formatRelativeTime(post.created_at);

    header.append(authorGroup, timeEl);

    const bodyEl = document.createElement("p");
    bodyEl.className = "post-body";
    bodyEl.textContent = post.body || "";

    card.append(header, bodyEl);

    if (post.image_url) {
      const img = document.createElement("img");
      img.src = post.image_url;
      img.alt = "Post attachment";
      img.className = "post-image";
      card.appendChild(img);
    }

    if (post.trending_reason) {
      const trendBadge = document.createElement("div");
      trendBadge.className = "form-hint";
      trendBadge.textContent = `Trending: ${post.trending_reason}`;
      card.appendChild(trendBadge);
    }

    const actions = document.createElement("div");
    actions.className = "post-actions";

    const likeBtn = document.createElement("button");
    likeBtn.type = "button";
    likeBtn.className = post.liked_by_me ? "btn btn-primary btn-sm" : "btn btn-outline btn-sm";
    let likeCount = post.like_count || 0;
    likeBtn.textContent = `♥ ${likeCount}`;
    likeBtn.addEventListener("click", async () => {
      try {
        const res = await api("POST", `/api/v1/posts/${post.id}/like`);
        likeCount = res.like_count;
        likeBtn.textContent = `♥ ${likeCount}`;
        likeBtn.className = res.liked ? "btn btn-primary btn-sm" : "btn btn-outline btn-sm";
      } catch (err) {
        showToast(err.message || "Could not update like.", "error");
      }
    });

    const commentsToggle = document.createElement("button");
    commentsToggle.type = "button";
    commentsToggle.className = "btn btn-outline btn-sm";
    let commentCount = post.comment_count || 0;
    commentsToggle.textContent = `💬 ${commentCount}`;

    const reportBtn = document.createElement("button");
    reportBtn.type = "button";
    reportBtn.className = "btn btn-outline btn-sm";
    reportBtn.textContent = "Report";
    reportBtn.addEventListener("click", async () => {
      const reason = window.prompt("Reason for reporting this post:");
      if (!reason || reason.trim().length < 3) return;
      try {
        await api("POST", "/api/v1/reports", {
          target_type: "post",
          target_id: post.id,
          reason: reason.trim(),
        });
        showToast("Report submitted.", "success");
      } catch (err) {
        showToast(err.message || "Could not submit report.", "error");
      }
    });

    actions.append(likeBtn, commentsToggle, reportBtn);
    card.appendChild(actions);

    const commentsPanel = document.createElement("div");
    commentsPanel.className = "comments-panel hidden";
    card.appendChild(commentsPanel);

    const renderComments = async () => {
      clearElement(commentsPanel);
      const listEl = document.createElement("div");
      listEl.className = "comments-list";
      try {
        const comments = await api("GET", `/api/v1/posts/${post.id}/comments`);
        if (!comments || comments.length === 0) {
          const empty = document.createElement("p");
          empty.className = "form-hint";
          empty.textContent = "No comments yet.";
          listEl.appendChild(empty);
        } else {
          comments.forEach((c) => {
            const row = document.createElement("div");
            row.className = "comment-item";
            const strong = document.createElement("strong");
            strong.textContent = `${c.author?.display_name || c.author?.username || "Student"}: `;
            const span = document.createElement("span");
            span.textContent = c.body;
            row.append(strong, span);
            listEl.appendChild(row);
            (c.replies || []).forEach((rep) => {
              const rRow = document.createElement("div");
              rRow.className = "comment-item comment-reply";
              const rStrong = document.createElement("strong");
              rStrong.textContent = `↳ ${rep.author?.display_name || rep.author?.username || "Student"}: `;
              const rSpan = document.createElement("span");
              rSpan.textContent = rep.body;
              rRow.append(rStrong, rSpan);
              listEl.appendChild(rRow);
            });
          });
        }
      } catch (err) {
        showToast(err.message || "Could not load comments.", "error");
      }

      const cForm = document.createElement("form");
      cForm.className = "skills-input-row";
      const cInput = document.createElement("input");
      cInput.type = "text";
      cInput.className = "form-input";
      cInput.placeholder = "Write a comment...";
      cInput.maxLength = 1000;
      const cBtn = document.createElement("button");
      cBtn.type = "submit";
      cBtn.className = "btn btn-primary btn-sm";
      cBtn.textContent = "Reply";
      cForm.append(cInput, cBtn);
      cForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = cInput.value.trim();
        if (!text) return;
        try {
          await api("POST", `/api/v1/posts/${post.id}/comments`, { body: text });
          commentCount += 1;
          commentsToggle.textContent = `💬 ${commentCount}`;
          await renderComments();
        } catch (err) {
          showToast(err.message || "Could not post comment.", "error");
        }
      });

      commentsPanel.append(listEl, cForm);
    };

    commentsToggle.addEventListener("click", async () => {
      const hidden = commentsPanel.classList.toggle("hidden");
      if (!hidden) {
        await renderComments();
      }
    });

    return card;
  }

  /**
   * Load feed items (initial or cursor-paginated).
   * @param {boolean} [append=false]
   */
  async function loadFeed(append = false) {
    const container = document.getElementById("feed-container");
    const loadMoreBtn = document.getElementById("load-more");
    if (!container || AppState.feedLoading) return;

    AppState.feedLoading = true;
    if (!append) {
      AppState.feedCursor = null;
      renderLoading(container, "Loading your campus feed...");
    } else if (loadMoreBtn) {
      loadMoreBtn.disabled = true;
      loadMoreBtn.textContent = "Loading...";
    }

    try {
      const url = AppState.feedCursor
        ? `/api/v1/feed?cursor=${encodeURIComponent(AppState.feedCursor)}`
        : "/api/v1/feed";
      const data = await api("GET", url);
      const posts = Array.isArray(data) ? data : data?.posts || [];
      const nextCursor = data?.next_cursor || null;

      if (!append) {
        clearElement(container);
      }

      if (posts.length === 0 && !append) {
        renderEmptyState(
          container,
          "Your feed is quiet",
          "Write a post above or connect with classmates to see campus updates here.",
          "📝",
          { label: "Discover Peers", href: "/discover" }
        );
      } else {
        posts.forEach((post) => container.appendChild(createPostCard(post)));
      }

      AppState.feedCursor = nextCursor;
      if (loadMoreBtn) {
        if (nextCursor) {
          loadMoreBtn.classList.remove("hidden");
          loadMoreBtn.disabled = false;
          loadMoreBtn.textContent = "Load More Posts";
        } else {
          loadMoreBtn.classList.add("hidden");
        }
      }
    } catch (err) {
      if (!append) {
        renderEmptyState(container, "Could not load feed", err.message, "⚠️");
      } else {
        showToast(err.message || "Failed to load more posts.", "error");
        if (loadMoreBtn) {
          loadMoreBtn.disabled = false;
          loadMoreBtn.textContent = "Load More Posts";
        }
      }
    } finally {
      AppState.feedLoading = false;
    }
  }

  function setupPostComposer() {
    const form = document.getElementById("post-composer-form");
    const textarea = document.getElementById("post-body");
    const submitBtn = document.getElementById("post-submit");
    const charCount = document.getElementById("post-char-count");
    const container = document.getElementById("feed-container");

    if (!form || !textarea || !submitBtn) return;

    const updateCounter = () => {
      if (!charCount) return;
      const len = textarea.value.length;
      charCount.textContent = `${len} / 5000`;
      charCount.classList.toggle("is-warning", len > 4500 && len <= 4900);
      charCount.classList.toggle("is-danger", len > 4900);
    };

    textarea.addEventListener("input", updateCounter);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = textarea.value.trim();
      if (!body) {
        showToast("Post body cannot be empty.", "warning");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Posting...";

      try {
        let newPost = await api("POST", "/api/v1/posts", { body });
        const imgInput = document.getElementById("post-image");
        if (imgInput && imgInput.files && imgInput.files[0]) {
          const fd = new FormData();
          fd.append("file", imgInput.files[0]);
          const uploadRes = await fetch(`/api/v1/posts/${newPost.id}/image`, {
            method: "POST",
            body: fd,
            credentials: "same-origin",
            headers: { "X-CSRF-Token": getCookie("csrf_token") },
          });
          if (uploadRes.ok) {
            const upData = await uploadRes.json();
            newPost.image_url = upData.image_url;
          }
          imgInput.value = "";
          const imgNameEl = document.getElementById("post-image-name");
          if (imgNameEl) imgNameEl.textContent = "";
        }
        textarea.value = "";
        updateCounter();
        showToast("Post published!", "success");

        if (container) {
          const empty = container.querySelector(".empty-state");
          if (empty) clearElement(container);
          container.prepend(createPostCard(newPost));
        }
      } catch (err) {
        showToast(err.message || "Failed to publish post.", "error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Post Update";
      }
    });
  }

  async function loadHomeSidebars() {
    const avatarEl = document.getElementById("sidebar-avatar");
    const nameEl = document.getElementById("sidebar-name");
    const subEl = document.getElementById("sidebar-sub");
    const connCountEl = document.getElementById("sidebar-conn-count");
    const reqCountEl = document.getElementById("sidebar-req-count");
    const suggWidget = document.getElementById("home-suggestions-widget");
    const groupsWidget = document.getElementById("home-groups-widget");

    if (!nameEl && !suggWidget) return;

    try {
      const [profile, conns, inReqs, outReqs, suggs, groups] = await Promise.all([
        api("GET", "/api/v1/me/profile").catch(() => null),
        api("GET", "/api/v1/connections").catch(() => []),
        api("GET", "/api/v1/connections/requests/incoming").catch(() => []),
        api("GET", "/api/v1/connections/requests/outgoing").catch(() => []),
        api("GET", "/api/v1/me/suggestions?limit=4").catch(() => []),
        api("GET", "/api/v1/groups/suggestions?limit=3").catch(() => []),
      ]);

      if (profile) {
        const dname = profile.display_name || profile.username;
        if (nameEl) {
          nameEl.textContent = dname;
          nameEl.href = profileUrl(profile.username);
        }
        if (subEl) {
          const deg = profile.degree_level || "UG";
          const parts = [profile.programme || "Campus Student", `${deg} · Year ${profile.year || 1}`];
          subEl.textContent = parts.join(" · ");
        }
        if (avatarEl) {
          if (profile.avatar_url) {
            clearElement(avatarEl);
            const img = document.createElement("img");
            img.src = profile.avatar_url;
            img.alt = dname;
            img.className = "avatar-img";
            avatarEl.appendChild(img);
          } else {
            avatarEl.textContent = getInitials(dname);
          }
        }
      }
      if (connCountEl) connCountEl.textContent = String(Array.isArray(conns) ? conns.length : 0);
      if (reqCountEl) {
        const totalPending =
          (Array.isArray(inReqs) ? inReqs.length : 0) +
          (Array.isArray(outReqs) ? outReqs.length : 0);
        reqCountEl.textContent = String(totalPending);
      }

      if (suggWidget) {
        clearElement(suggWidget);
        if (!suggs || suggs.length === 0) {
          const empty = document.createElement("p");
          empty.className = "form-hint";
          empty.textContent = "No new suggestions right now.";
          suggWidget.appendChild(empty);
        } else {
          suggs.forEach((item) => {
            const u = item.user || {};
            const row = document.createElement("div");
            row.className = "widget-item";
            const info = document.createElement("div");
            info.className = "widget-item-info";
            const link = document.createElement("a");
            link.href = profileUrl(u.username);
            link.className = "widget-item-name";
            link.textContent = u.display_name || u.username;
            const sub = document.createElement("div");
            sub.className = "widget-item-sub";
            sub.textContent = item.reason || "Campus peer";
            info.append(link, sub);

            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn btn-outline btn-sm";
            btn.textContent = "Connect";
            btn.addEventListener("click", async () => {
              btn.disabled = true;
              try {
                await sendConnectionRequest(u.user_id, u.username);
                btn.textContent = "Sent";
                showToast(`Request sent to @${u.username}.`, "success");
              } catch (err) {
                btn.disabled = false;
                showToast(err.message || "Could not send request.", "error");
              }
            });
            row.append(info, btn);
            suggWidget.appendChild(row);
          });
        }
      }

      if (groupsWidget) {
        clearElement(groupsWidget);
        if (!groups || groups.length === 0) {
          const empty = document.createElement("p");
          empty.className = "form-hint";
          empty.textContent = "Explore or create a campus group.";
          groupsWidget.appendChild(empty);
        } else {
          groups.forEach((g) => {
            const row = document.createElement("div");
            row.className = "widget-item";
            const info = document.createElement("div");
            info.className = "widget-item-info";
            const link = document.createElement("a");
            link.href = "/groups";
            link.className = "widget-item-name";
            link.textContent = g.name;
            const sub = document.createElement("div");
            sub.className = "widget-item-sub";
            sub.textContent = `${g.member_count} members · ${g.reason}`;
            info.append(link, sub);
            row.appendChild(info);
            groupsWidget.appendChild(row);
          });
        }
      }
    } catch (_) {}
  }

  function initHomePage() {
    setupPostComposer();
    loadFeed(false);
    loadHomeSidebars();

    const imgInput = document.getElementById("post-image");
    const imgNameEl = document.getElementById("post-image-name");
    if (imgInput && imgNameEl) {
      imgInput.addEventListener("change", () => {
        imgNameEl.textContent = imgInput.files?.[0]?.name || "";
      });
    }

    const recentBtn = document.getElementById("feed-tab-recent");
    const trendingBtn = document.getElementById("feed-tab-trending");
    const loadMoreBtn = document.getElementById("load-more");

    if (recentBtn && trendingBtn) {
      recentBtn.addEventListener("click", () => {
        recentBtn.className = "btn btn-primary btn-sm";
        trendingBtn.className = "btn btn-outline btn-sm";
        loadFeed(false);
      });
      trendingBtn.addEventListener("click", async () => {
        trendingBtn.className = "btn btn-primary btn-sm";
        recentBtn.className = "btn btn-outline btn-sm";
        if (loadMoreBtn) loadMoreBtn.classList.add("hidden");
        const container = document.getElementById("feed-container");
        if (!container) return;
        renderLoading(container, "Computing trending posts...");
        try {
          const posts = await api("GET", "/api/v1/feed/trending");
          clearElement(container);
          if (!posts || posts.length === 0) {
            renderEmptyState(
              container,
              "No trending posts yet",
              "Posts liked or commented on by your connections in the last 7 days will appear here.",
              "🔥"
            );
          } else {
            posts.forEach((p) => container.appendChild(createPostCard(p)));
          }
        } catch (err) {
          renderEmptyState(container, "Could not load trending", err.message, "⚠️");
        }
      });
    }

    if (loadMoreBtn) {
      loadMoreBtn.addEventListener("click", () => loadFeed(true));
    }
  }

  /* ========================================================================
     7. Profile Page (View User, Mutuals, Shortest Path, Connect Action)
     ======================================================================== */

  /**
   * Extract target username from query string (?username=...) or path (/profile/{username}).
   * Falls back to current user's username.
   * @returns {string|null}
   */
  function getTargetProfileUsername() {
    const params = new URLSearchParams(window.location.search);
    const qUser = params.get("username");
    if (qUser) return qUser.trim();

    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts.length >= 2 && (parts[0] === "profile" || parts[0] === "users")) {
      return decodeURIComponent(parts[1]);
    }
    return AppState.currentUser?.username || null;
  }

  /**
   * Send a connection request to a target user.
   * @param {number} userId
   * @param {string} username
   * @returns {Promise<any>}
   */
  async function sendConnectionRequest(userId, username) {
    const res = await api("POST", "/api/v1/connections/requests", {
      receiver_id: userId,
      username,
    });
    const reqCountEl = document.getElementById("sidebar-req-count");
    if (reqCountEl) {
      const cur = Number.parseInt(reqCountEl.textContent || "0", 10) || 0;
      reqCountEl.textContent = String(cur + 1);
    }
    return res;
  }

  function renderProfile(profile) {
    const avatarEl = document.getElementById("profile-avatar");
    const nameEl = document.getElementById("profile-name");
    const usernameEl = document.getElementById("profile-username");
    const programmeEl = document.getElementById("profile-programme");
    const yearEl = document.getElementById("profile-year");
    const bioEl = document.getElementById("profile-bio");
    const skillsEl = document.getElementById("profile-skills");
    const countEl = document.getElementById("connection-count");
    const actionBtn = document.getElementById("connection-action");

    const displayName = profile.display_name || profile.username;
    document.title = `${displayName} — CampusHive`;

    if (avatarEl) {
      if (profile.avatar_url) {
        clearElement(avatarEl);
        const img = document.createElement("img");
        img.src = profile.avatar_url;
        img.alt = displayName;
        img.className = "avatar-img";
        avatarEl.appendChild(img);
      } else {
        avatarEl.textContent = getInitials(displayName);
      }
    }
    if (nameEl) nameEl.textContent = displayName;
    if (usernameEl) usernameEl.textContent = `@${profile.username}`;
    if (programmeEl) {
      programmeEl.textContent = profile.programme || "Programme not set";
    }
    if (yearEl) {
      const deg = profile.degree_level || "UG";
      yearEl.textContent = profile.year ? `${deg} · Year ${profile.year}` : deg;
    }
    if (bioEl) {
      bioEl.textContent = profile.bio || "No bio provided yet.";
    }
    if (countEl) {
      const count = typeof profile.connection_count === "number"
        ? profile.connection_count
        : null;
      if (count !== null) {
        countEl.textContent = `${count} connection${count === 1 ? "" : "s"}`;
      } else {
        countEl.textContent = profile.is_connected ? "Connected" : "Campus member";
      }
    }

    if (skillsEl) {
      clearElement(skillsEl);
      const skills = Array.isArray(profile.skills) ? profile.skills : [];
      if (skills.length === 0) {
        const emptyHint = document.createElement("span");
        emptyHint.className = "form-hint";
        emptyHint.textContent = "No skills listed yet.";
        skillsEl.appendChild(emptyHint);
      } else {
        skills.forEach((skill, idx) => {
          const tag = document.createElement("span");
          tag.className = `skill-tag skill-tag-color-${(idx % 4) + 1}`;
          tag.textContent = skill;
          skillsEl.appendChild(tag);
        });
      }
    }

    if (actionBtn) {
      configureProfileActionButton(actionBtn, profile);
    }

    const blockBtn = document.getElementById("block-action");
    const reportBtn = document.getElementById("report-action");
    const isSelf = AppState.currentUser && AppState.currentUser.id === profile.user_id;
    if (blockBtn && reportBtn && !isSelf) {
      blockBtn.classList.remove("hidden");
      reportBtn.classList.remove("hidden");
      blockBtn.textContent = profile.is_blocked ? "Unblock" : "Block";
      blockBtn.onclick = async () => {
        try {
          if (profile.is_blocked) {
            await api("DELETE", `/api/v1/users/${encodeURIComponent(profile.username)}/block`);
            showToast("User unblocked.", "info");
          } else {
            await api("POST", `/api/v1/users/${encodeURIComponent(profile.username)}/block`);
            showToast("User blocked.", "info");
          }
          await loadProfile(profile.username);
        } catch (err) {
          showToast(err.message || "Could not update block status.", "error");
        }
      };
      reportBtn.onclick = async () => {
        const reason = window.prompt(`Reason for reporting @${profile.username}:`);
        if (!reason || reason.trim().length < 3) return;
        try {
          await api("POST", "/api/v1/reports", {
            target_type: "user",
            target_id: profile.user_id,
            reason: reason.trim(),
          });
          showToast("Report submitted.", "success");
        } catch (err) {
          showToast(err.message || "Could not submit report.", "error");
        }
      };
    }
  }

  function configureProfileActionButton(btn, profile) {
    const isSelf = AppState.currentUser && AppState.currentUser.id === profile.user_id;
    if (isSelf) {
      btn.classList.remove("hidden");
      btn.className = "btn btn-secondary";
      btn.textContent = "Edit My Profile";
      btn.disabled = false;
      btn.onclick = () => {
        window.location.href = "/my-profile";
      };
      return;
    }

    btn.classList.remove("hidden");
    const status = profile.connection_status;

    if (profile.is_connected || status === "connected" || status === "accepted") {
      btn.className = "btn btn-outline-danger";
      btn.textContent = "Remove Connection";
      btn.disabled = false;
      btn.onclick = async () => {
        btn.disabled = true;
        btn.textContent = "Removing...";
        try {
          await api("DELETE", `/api/v1/connections/${profile.user_id}`);
          showToast(`Removed @${profile.username} from connections.`, "info");
          profile.is_connected = false;
          profile.connection_status = null;
          configureProfileActionButton(btn, profile);
          loadPath(profile.username);
        } catch (err) {
          showToast(err.message || "Could not remove connection.", "error");
          btn.disabled = false;
          btn.textContent = "Remove Connection";
        }
      };
    } else if (status === "pending_sent" || status === "outgoing") {
      btn.className = "btn btn-secondary";
      btn.textContent = "Request Sent";
      btn.disabled = true;
      btn.onclick = null;
    } else if (status === "pending_received" || status === "incoming") {
      btn.className = "btn btn-primary";
      btn.textContent = "Respond to Request";
      btn.disabled = false;
      btn.onclick = () => {
        window.location.href = "/requests";
      };
    } else {
      btn.className = "btn btn-primary";
      btn.textContent = "Connect";
      btn.disabled = false;
      btn.onclick = async () => {
        btn.disabled = true;
        btn.textContent = "Sending...";
        try {
          await sendConnectionRequest(profile.user_id, profile.username);
          showToast(`Connection request sent to @${profile.username}.`, "success");
          profile.connection_status = "pending_sent";
          configureProfileActionButton(btn, profile);
        } catch (err) {
          showToast(err.message || "Failed to send request.", "error");
          btn.disabled = false;
          btn.textContent = "Connect";
        }
      };
    }
  }

  async function loadMutualConnections(username) {
    const container = document.getElementById("mutual-connections");
    if (!container) return;

    if (AppState.currentUser && AppState.currentUser.username === username) {
      renderEmptyState(container, "Your Profile", "Mutual connections appear when viewing another student's profile.", "👤");
      return;
    }

    try {
      const data = await api("GET", `/api/v1/users/${encodeURIComponent(username)}/mutual`);
      const mutuals = data?.mutual_connections || [];
      clearElement(container);

      if (mutuals.length === 0) {
        renderEmptyState(container, "No mutual connections", "You don't share any direct connections yet.", "🤝");
        return;
      }

      const list = document.createElement("div");
      list.className = "mutual-list";

      mutuals.forEach((user) => {
        const item = document.createElement("a");
        item.href = profileUrl(user.username);
        item.className = "mutual-item";

        const info = document.createElement("div");
        info.className = "mutual-item-info";
        const avatar = createAvatar(user.display_name || user.username, "avatar-sm");

        const textWrap = document.createElement("div");
        const nameEl = document.createElement("div");
        nameEl.className = "user-card-name";
        nameEl.textContent = user.display_name || user.username;
        const subEl = document.createElement("div");
        subEl.className = "user-card-username";
        subEl.textContent = `@${user.username}`;
        textWrap.append(nameEl, subEl);

        info.append(avatar, textWrap);
        item.appendChild(info);
        list.appendChild(item);
      });

      container.appendChild(list);
    } catch (err) {
      renderEmptyState(container, "Unavailable", err.message || "Could not load mutual connections.", "⚠️");
    }
  }

  async function loadPath(username) {
    const container = document.getElementById("path-section");
    const degreeBadge = document.getElementById("profile-degree-badge");
    if (!container) return;

    if (AppState.currentUser && AppState.currentUser.username === username) {
      if (degreeBadge) {
        degreeBadge.textContent = "Self";
        degreeBadge.className = "degree-badge degree-1st";
      }
      renderEmptyState(container, "This is you", "View another student's profile to trace your shortest campus connection path.", "🧭");
      return;
    }

    try {
      const data = await api("GET", `/api/v1/users/${encodeURIComponent(username)}/path`);
      const path = data?.path || [];
      const hops = data?.hop_count;
      const label = data?.degree_label || "Not connected";

      if (degreeBadge) {
        degreeBadge.textContent = label;
        degreeBadge.classList.remove("hidden", "degree-1st", "degree-2nd", "degree-3rd", "degree-distant");
        if (hops === 1) degreeBadge.classList.add("degree-1st");
        else if (hops === 2) degreeBadge.classList.add("degree-2nd");
        else if (hops === 3) degreeBadge.classList.add("degree-3rd");
        else degreeBadge.classList.add("degree-distant");
      }

      clearElement(container);

      if (!path || path.length === 0) {
        renderEmptyState(container, "No connection path", "No path exists between you and this user yet.", "🕸️");
        return;
      }

      const summary = document.createElement("p");
      summary.className = "page-subtitle";
      summary.style.marginBottom = "0.75rem";
      summary.textContent = `${label} (${hops} hop${hops === 1 ? "" : "s"})`;

      const chain = document.createElement("div");
      chain.className = "path-chain";

      path.forEach((node, index) => {
        const nodeEl = document.createElement("a");
        nodeEl.href = profileUrl(node.username);
        nodeEl.className = "path-node";

        const av = createAvatar(node.display_name || node.username, "avatar-sm");
        const lbl = document.createElement("span");
        lbl.textContent = node.display_name || `@${node.username}`;
        nodeEl.append(av, lbl);
        chain.appendChild(nodeEl);

        if (index < path.length - 1) {
          const arrow = document.createElement("span");
          arrow.className = "path-arrow";
          arrow.setAttribute("aria-hidden", "true");
          arrow.textContent = "→";
          chain.appendChild(arrow);
        }
      });

      container.append(summary, chain);
    } catch (err) {
      renderEmptyState(container, "Path unavailable", err.message || "Could not compute shortest path.", "⚠️");
    }
  }

  async function loadProfilePosts(username) {
    const container = document.getElementById("profile-posts-list");
    if (!container) return;
    renderLoading(container, "Loading posts...");
    try {
      const posts = await api("GET", `/api/v1/users/${encodeURIComponent(username)}/posts`);
      clearElement(container);
      if (!posts || posts.length === 0) {
        renderEmptyState(container, "No posts yet", "Posts shared by this student will appear here.", "📝");
        return;
      }
      posts.forEach((post) => container.appendChild(createPostCard(post)));
    } catch (err) {
      renderEmptyState(container, "Could not load posts", err.message || "Unavailable.", "⚠️");
    }
  }

  async function loadProfileSuggestions(excludeUsername) {
    const container = document.getElementById("profile-suggestions-list");
    if (!container) return;
    renderLoading(container, "Finding mutual suggestions...");
    try {
      const suggs = await api("GET", "/api/v1/me/suggestions?limit=6");
      const filtered = (suggs || []).filter((s) => s.user?.username !== excludeUsername);
      clearElement(container);
      if (filtered.length === 0) {
        renderEmptyState(container, "No new suggestions", "Check Discover for more campus peers.");
        return;
      }
      filtered.slice(0, 4).forEach((item) => {
        const u = item.user || {};
        const viewLink = document.createElement("a");
        viewLink.href = profileUrl(u.username);
        viewLink.className = "btn btn-outline btn-sm";
        viewLink.textContent = "View";

        const connectBtn = document.createElement("button");
        connectBtn.type = "button";
        connectBtn.className = "btn btn-primary btn-sm";
        connectBtn.textContent = "Connect";
        connectBtn.addEventListener("click", async () => {
          connectBtn.disabled = true;
          try {
            await sendConnectionRequest(u.user_id, u.username);
            connectBtn.textContent = "Sent";
            showToast(`Request sent to @${u.username}.`, "success");
          } catch (err) {
            connectBtn.disabled = false;
            showToast(err.message || "Could not send request.", "error");
          }
        });

        const card = createUserCard(u, [viewLink, connectBtn]);
        const reasonEl = document.createElement("div");
        reasonEl.className = "form-hint";
        reasonEl.style.padding = "0 0 0.5rem";
        reasonEl.textContent = item.reason || "";
        card.insertBefore(reasonEl, card.lastElementChild);
        container.appendChild(card);
      });
    } catch (err) {
      renderEmptyState(container, "Suggestions unavailable", err.message || "Try again later.");
    }
  }

  async function loadProfile(username) {
    const profileCard = document.getElementById("profile-card");
    if (!username) {
      if (profileCard) {
        renderEmptyState(profileCard, "No user specified", "Provide a username to view their profile.", "");
      }
      return;
    }

    try {
      const profile = await api("GET", `/api/v1/users/${encodeURIComponent(username)}`);
      renderProfile(profile);
      await Promise.all([
        loadMutualConnections(profile.username),
        loadPath(profile.username),
        loadProfilePosts(profile.username),
        loadProfileSuggestions(profile.username),
      ]);
    } catch (err) {
      if (profileCard) {
        renderEmptyState(profileCard, "Profile not found", err.message || "This user could not be found.", "🔍", {
          label: "Search Directory",
          href: "/search",
        });
      }
      const mutuals = document.getElementById("mutual-connections");
      const pathSec = document.getElementById("path-section");
      if (mutuals) clearElement(mutuals);
      if (pathSec) clearElement(pathSec);
    }
  }

  function initProfilePage() {
    const username = getTargetProfileUsername();
    loadProfile(username);
    const copyBtn = document.getElementById("copy-profile-url");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        copyToClipboard(window.location.href, "Profile link");
      });
    }
  }

  /* ========================================================================
     8. My Profile Editor Page
     ======================================================================== */
  function renderMySkillTags() {
    const container = document.getElementById("skills-tags");
    if (!container) return;
    clearElement(container);

    if (AppState.mySkills.length === 0) {
      const hint = document.createElement("span");
      hint.className = "form-hint";
      hint.textContent = "No skills added yet.";
      container.appendChild(hint);
      return;
    }

    AppState.mySkills.forEach((skill, index) => {
      const tag = document.createElement("span");
      tag.className = `skill-tag skill-tag-removable skill-tag-color-${(index % 4) + 1}`;

      const label = document.createElement("span");
      label.textContent = skill;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "skill-tag-remove";
      removeBtn.setAttribute("aria-label", `Remove ${skill}`);
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", () => {
        AppState.mySkills.splice(index, 1);
        renderMySkillTags();
      });

      tag.append(label, removeBtn);
      container.appendChild(tag);
    });
  }

  function addSkillFromInput() {
    const input = document.getElementById("skills");
    if (!input) return;
    const raw = input.value.trim();
    if (!raw) return;

    const candidates = raw.split(",").map((s) => s.trim()).filter(Boolean);
    for (const skill of candidates) {
      if (AppState.mySkills.length >= 20) {
        showToast("Maximum of 20 skills allowed.", "warning");
        break;
      }
      const exists = AppState.mySkills.some((s) => s.toLowerCase() === skill.toLowerCase());
      if (!exists) {
        AppState.mySkills.push(skill);
      }
    }
    input.value = "";
    renderMySkillTags();
  }

  async function loadMyProfile() {
    const displayNameInput = document.getElementById("display_name");
    const programmeInput = document.getElementById("programme");
    const yearInput = document.getElementById("year");
    const bioInput = document.getElementById("bio");
    const bioCount = document.getElementById("bio-char-count");
    const publicLink = document.getElementById("view-public-profile-link");

    if (publicLink && AppState.currentUser) {
      publicLink.href = profileUrl(AppState.currentUser.username);
    }

    try {
      const profile = await api("GET", "/api/v1/me/profile");
      if (displayNameInput) displayNameInput.value = profile.display_name || "";
      if (programmeInput) programmeInput.value = profile.programme || "";
      const degreeInput = document.getElementById("degree_level");
      const level = profile.degree_level || "UG";
      if (degreeInput) degreeInput.value = level;
      syncYearOptionsForDegree(level, profile.year || 1);
      if (bioInput) {
        bioInput.value = profile.bio || "";
        if (bioCount) bioCount.textContent = `${bioInput.value.length} / 500`;
      }
      const visInput = document.getElementById("visibility");
      if (visInput && profile.visibility) visInput.value = profile.visibility;
      AppState.mySkills = Array.isArray(profile.skills) ? [...profile.skills] : [];
      renderMySkillTags();
    } catch (err) {
      showToast(err.message || "Failed to load your profile.", "error");
    }
  }

  async function saveProfile(e) {
    e.preventDefault();
    const errorBox = document.getElementById("my-profile-error");
    const saveBtn = document.getElementById("save-profile");
    const displayNameInput = document.getElementById("display_name");
    const programmeInput = document.getElementById("programme");
    const yearInput = document.getElementById("year");
    const bioInput = document.getElementById("bio");

    if (errorBox) errorBox.textContent = "";

    // Capture any pending unsubmitted text in the skills input
    addSkillFromInput();

    const visInput = document.getElementById("visibility");
    const degreeInput = document.getElementById("degree_level");
    const payload = {
      display_name: displayNameInput?.value.trim() || "",
      programme: programmeInput?.value.trim() || "",
      degree_level: degreeInput?.value || "UG",
      year: yearInput ? Number.parseInt(yearInput.value, 10) : 1,
      bio: bioInput?.value.trim() || "",
      skills: AppState.mySkills,
      visibility: visInput?.value || "campus",
    };

    if (payload.display_name.length > 100) {
      if (errorBox) errorBox.textContent = "Display name must be at most 100 characters.";
      return;
    }
    if (payload.bio.length > 500) {
      if (errorBox) errorBox.textContent = "Bio must be at most 500 characters.";
      return;
    }

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving...";
    }

    try {
      await api("PATCH", "/api/v1/me/profile", payload);
      showToast("Profile updated successfully!", "success");
    } catch (err) {
      if (errorBox) errorBox.textContent = err.message || "Failed to save profile.";
      showToast(err.message || "Could not save profile.", "error");
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save Profile";
      }
    }
  }

  function initMyProfilePage() {
    loadMyProfile();

    const degreeInput = document.getElementById("degree_level");
    if (degreeInput) {
      degreeInput.addEventListener("change", () => {
        syncYearOptionsForDegree(degreeInput.value);
      });
    }

    const form = document.getElementById("profile-edit-form");
    const bioInput = document.getElementById("bio");
    const bioCount = document.getElementById("bio-char-count");
    const skillInput = document.getElementById("skills");
    const addSkillBtn = document.getElementById("add-skill-btn");

    if (bioInput && bioCount) {
      bioInput.addEventListener("input", () => {
        bioCount.textContent = `${bioInput.value.length} / 500`;
      });
    }

    if (skillInput) {
      skillInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          addSkillFromInput();
        }
      });
    }

    if (addSkillBtn) {
      addSkillBtn.addEventListener("click", addSkillFromInput);
    }

    if (form) {
      form.addEventListener("submit", saveProfile);
    }

    const uploadAvatarBtn = document.getElementById("upload-avatar-btn");
    const avatarInput = document.getElementById("avatar-upload");
    if (uploadAvatarBtn && avatarInput) {
      uploadAvatarBtn.addEventListener("click", async () => {
        if (!avatarInput.files?.[0]) {
          showToast("Choose a JPEG, PNG, or WebP file first.", "warning");
          return;
        }
        const fd = new FormData();
        fd.append("file", avatarInput.files[0]);
        try {
          const res = await fetch("/api/v1/me/avatar", {
            method: "POST",
            body: fd,
            credentials: "same-origin",
            headers: { "X-CSRF-Token": getCookie("csrf_token") },
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.message || "Avatar upload failed");
          }
          showToast("Profile photo updated!", "success");
          avatarInput.value = "";
        } catch (err) {
          showToast(err.message || "Could not upload photo.", "error");
        }
      });
    }

    const removeAvatarBtn = document.getElementById("remove-avatar-btn");
    if (removeAvatarBtn) {
      removeAvatarBtn.addEventListener("click", async () => {
        try {
          await api("DELETE", "/api/v1/me/avatar");
          showToast("Profile photo removed.", "info");
        } catch (err) {
          showToast(err.message || "Could not remove photo.", "error");
        }
      });
    }

    const exportBtn = document.getElementById("export-data-btn");
    if (exportBtn) {
      exportBtn.addEventListener("click", async () => {
        try {
          const data = await api("GET", "/api/v1/me/export");
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "campusconnect_export.json";
          a.click();
          URL.revokeObjectURL(url);
        } catch (err) {
          showToast(err.message || "Could not export data.", "error");
        }
      });
    }

    const deleteBtn = document.getElementById("delete-account-btn");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", async () => {
        const confirmed = await showConfirmModal({
          title: "Delete Account",
          message: "This will permanently delete your account, profile, connections, and posts. This action cannot be undone.",
          confirmLabel: "Delete Permanently",
        });
        if (!confirmed) return;
        try {
          await api("DELETE", "/api/v1/me/account");
          window.location.replace("/");
        } catch (err) {
          showToast(err.message || "Could not delete account.", "error");
        }
      });
    }
  }

  /* ========================================================================
     8b. Groups Page
     ======================================================================== */
  async function loadGroupsPageData() {
    const suggContainer = document.getElementById("group-suggestions-list");
    const allContainer = document.getElementById("all-groups-list");
    if (suggContainer) renderLoading(suggContainer, "Finding closely connected groups...");
    if (allContainer) renderLoading(allContainer, "Loading groups...");

    try {
      const [suggs, allGroups] = await Promise.all([
        api("GET", "/api/v1/groups/suggestions"),
        api("GET", "/api/v1/groups"),
      ]);

      if (suggContainer) {
        clearElement(suggContainer);
        if (!suggs || suggs.length === 0) {
          renderEmptyState(
            suggContainer,
            "No group suggestions yet",
            "Group suggestions appear for campus-visible groups with at least 3 active members.",
            "👥"
          );
        } else {
          suggs.forEach((g) => {
            const card = document.createElement("article");
            card.className = "card user-card";
            const title = document.createElement("h3");
            title.textContent = g.name;
            const desc = document.createElement("p");
            desc.className = "form-hint";
            desc.textContent = `${g.description || "Campus group"} · ${g.member_count} members · Score ${g.score}`;
            const joinBtn = document.createElement("button");
            joinBtn.type = "button";
            joinBtn.className = "btn btn-primary btn-sm";
            joinBtn.textContent = g.membership_policy === "request" ? "Request Join" : "Join Group";
            joinBtn.addEventListener("click", async () => {
              try {
                await api("POST", `/api/v1/groups/${g.id}/join`);
                showToast(`Joined ${g.name}!`, "success");
                await loadGroupsPageData();
              } catch (err) {
                showToast(err.message || "Could not join group.", "error");
              }
            });
            card.append(title, desc, joinBtn);
            suggContainer.appendChild(card);
          });
        }
      }

      if (allContainer) {
        clearElement(allContainer);
        if (!allGroups || allGroups.length === 0) {
          renderEmptyState(allContainer, "No groups yet", "Create the first campus group above!", "🏫");
        } else {
          allGroups.forEach((g) => {
            const card = document.createElement("article");
            card.className = "card user-card";
            const title = document.createElement("h3");
            title.textContent = g.name;
            const desc = document.createElement("p");
            desc.className = "form-hint";
            desc.textContent = `${g.description || "No description"} · ${g.member_count} members · ${g.membership_policy}`;
            const footer = document.createElement("div");
            if (g.my_status === "active" && g.my_role !== "owner") {
              const leaveBtn = document.createElement("button");
              leaveBtn.type = "button";
              leaveBtn.className = "btn btn-outline-danger btn-sm";
              leaveBtn.textContent = "Leave";
              leaveBtn.addEventListener("click", async () => {
                try {
                  await api("DELETE", `/api/v1/groups/${g.id}/leave`);
                  showToast("Left group.", "info");
                  await loadGroupsPageData();
                } catch (err) {
                  showToast(err.message || "Could not leave group.", "error");
                }
              });
              footer.appendChild(leaveBtn);
            } else if (g.my_role === "owner") {
              const badge = document.createElement("span");
              badge.className = "profile-meta-pill";
              badge.textContent = "Owner";
              footer.appendChild(badge);
            } else if (g.my_status === "pending") {
              const badge = document.createElement("span");
              badge.className = "profile-meta-pill";
              badge.textContent = "Pending";
              footer.appendChild(badge);
            } else if (g.membership_policy !== "invite") {
              const joinBtn = document.createElement("button");
              joinBtn.type = "button";
              joinBtn.className = "btn btn-primary btn-sm";
              joinBtn.textContent = g.membership_policy === "request" ? "Request Join" : "Join";
              joinBtn.addEventListener("click", async () => {
                try {
                  await api("POST", `/api/v1/groups/${g.id}/join`);
                  showToast(`Joined ${g.name}!`, "success");
                  await loadGroupsPageData();
                } catch (err) {
                  showToast(err.message || "Could not join group.", "error");
                }
              });
              footer.appendChild(joinBtn);
            }
            card.append(title, desc, footer);
            allContainer.appendChild(card);
          });
        }
      }
    } catch (err) {
      if (allContainer) renderEmptyState(allContainer, "Could not load groups", err.message, "⚠️");
    }
  }

  function initGroupsPage() {
    loadGroupsPageData();
    const form = document.getElementById("create-group-form");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = document.getElementById("group-name")?.value.trim() || "";
        const description = document.getElementById("group-desc")?.value.trim() || "";
        const membership_policy = document.getElementById("group-policy")?.value || "open";
        if (name.length < 2) {
          showToast("Group name must be at least 2 characters.", "warning");
          return;
        }
        try {
          await api("POST", "/api/v1/groups", { name, description, membership_policy });
          form.reset();
          showToast("Group created!", "success");
          await loadGroupsPageData();
        } catch (err) {
          showToast(err.message || "Could not create group.", "error");
        }
      });
    }
  }

  /* ========================================================================
     9. Connections Page
     ======================================================================== */
  function createUserCard(user, footerContent) {
    const card = document.createElement("article");
    card.className = "card card-hover user-card";

    const top = document.createElement("div");
    top.className = "user-card-top";

    const displayName = user.display_name || user.username || "Student";
    const avatar = createAvatar(displayName, "avatar-md");

    const info = document.createElement("div");
    info.className = "user-card-info";

    const nameLink = document.createElement("a");
    nameLink.href = profileUrl(user.username);
    nameLink.className = "user-card-name";
    nameLink.textContent = displayName;

    const usernameEl = document.createElement("div");
    usernameEl.className = "user-card-username";
    usernameEl.textContent = `@${user.username}`;

    const metaEl = document.createElement("div");
    metaEl.className = "user-card-meta";
    const metaParts = [];
    if (user.programme) metaParts.push(user.programme);
    if (user.year) metaParts.push(`Year ${user.year}`);
    metaEl.textContent = metaParts.join(" · ") || "Campus member";

    info.append(nameLink, usernameEl, metaEl);
    top.append(avatar, info);

    const footer = document.createElement("div");
    footer.className = "user-card-footer";
    if (Array.isArray(footerContent)) {
      footerContent.forEach((node) => footer.appendChild(node));
    } else if (footerContent) {
      footer.appendChild(footerContent);
    }

    card.append(top, footer);
    return card;
  }

  async function loadConnections() {
    const grid = document.getElementById("connections-grid");
    if (!grid) return;
    renderLoading(grid, "Loading connections...");

    try {
      const data = await api("GET", "/api/v1/connections");
      const connections = Array.isArray(data) ? data : data?.connections || [];
      clearElement(grid);

      if (connections.length === 0) {
        renderEmptyState(
          grid,
          "No connections yet",
          "Start building your campus graph by exploring suggested peers or searching the directory.",
          "🌐",
          { label: "Discover People", href: "/discover" }
        );
        return;
      }

      connections.forEach((conn) => {
        const user = conn.user || conn;
        const since = document.createElement("span");
        since.className = "form-hint";
        since.textContent = conn.connected_since
          ? `Connected ${formatRelativeTime(conn.connected_since)}`
          : "Connected";

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "btn btn-outline-danger btn-sm";
        removeBtn.textContent = "Remove";

        let cardRef = null;
        removeBtn.addEventListener("click", async () => {
          removeBtn.disabled = true;
          removeBtn.textContent = "Removing...";
          try {
            await api("DELETE", `/api/v1/connections/${user.user_id}`);
            showToast(`Removed @${user.username} from connections.`, "info");
            if (cardRef) cardRef.remove();
            if (grid.children.length === 0) {
              renderEmptyState(
                grid,
                "No connections yet",
                "Start building your campus graph by exploring suggested peers.",
                "🌐",
                { label: "Discover People", href: "/discover" }
              );
            }
          } catch (err) {
            showToast(err.message || "Failed to remove connection.", "error");
            removeBtn.disabled = false;
            removeBtn.textContent = "Remove";
          }
        });

        cardRef = createUserCard(user, [since, removeBtn]);
        grid.appendChild(cardRef);
      });
    } catch (err) {
      renderEmptyState(grid, "Could not load connections", err.message, "⚠️");
    }
  }

  function initConnectionsPage() {
    loadConnections();
  }

  /* ========================================================================
     10. Requests Page (Incoming / Outgoing Tabs)
     ======================================================================== */
  function createRequestCard(req, direction) {
    const card = document.createElement("article");
    card.className = "card request-card";
    card.dataset.requestId = String(req.id);

    const peer = direction === "incoming" ? req.sender : req.receiver;
    const displayName = peer?.display_name || peer?.username || "Student";

    const userBlock = document.createElement("div");
    userBlock.className = "request-card-user";
    const avatar = createAvatar(displayName, "avatar-md");

    const info = document.createElement("div");
    const nameLink = document.createElement("a");
    nameLink.href = profileUrl(peer.username);
    nameLink.className = "user-card-name";
    nameLink.textContent = displayName;

    const sub = document.createElement("div");
    sub.className = "user-card-meta";
    const parts = [`@${peer.username}`];
    if (peer.programme) parts.push(peer.programme);
    if (req.created_at) parts.push(formatRelativeTime(req.created_at));
    sub.textContent = parts.join(" · ");

    info.append(nameLink, sub);
    userBlock.append(avatar, info);

    const actions = document.createElement("div");
    actions.className = "request-card-actions";

    if (direction === "incoming") {
      const acceptBtn = document.createElement("button");
      acceptBtn.type = "button";
      acceptBtn.className = "btn btn-primary btn-sm";
      acceptBtn.textContent = "Accept";

      const rejectBtn = document.createElement("button");
      rejectBtn.type = "button";
      rejectBtn.className = "btn btn-secondary btn-sm";
      rejectBtn.textContent = "Decline";

      acceptBtn.addEventListener("click", async () => {
        acceptBtn.disabled = true;
        rejectBtn.disabled = true;
        try {
          await api("POST", `/api/v1/connections/requests/${req.id}/accept`);
          showToast(`You are now connected with @${peer.username}!`, "success");
          card.remove();
          checkEmptyRequests("incoming");
        } catch (err) {
          showToast(err.message || "Could not accept request.", "error");
          acceptBtn.disabled = false;
          rejectBtn.disabled = false;
        }
      });

      rejectBtn.addEventListener("click", async () => {
        acceptBtn.disabled = true;
        rejectBtn.disabled = true;
        try {
          await api("POST", `/api/v1/connections/requests/${req.id}/reject`);
          showToast(`Declined request from @${peer.username}.`, "info");
          card.remove();
          checkEmptyRequests("incoming");
        } catch (err) {
          showToast(err.message || "Could not decline request.", "error");
          acceptBtn.disabled = false;
          rejectBtn.disabled = false;
        }
      });

      actions.append(acceptBtn, rejectBtn);
    } else {
      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.className = "btn btn-outline-danger btn-sm";
      cancelBtn.textContent = "Cancel Request";

      cancelBtn.addEventListener("click", async () => {
        cancelBtn.disabled = true;
        cancelBtn.textContent = "Cancelling...";
        try {
          await api("DELETE", `/api/v1/connections/requests/${req.id}`);
          showToast(`Cancelled request to @${peer.username}.`, "info");
          card.remove();
          checkEmptyRequests("outgoing");
        } catch (err) {
          showToast(err.message || "Could not cancel request.", "error");
          cancelBtn.disabled = false;
          cancelBtn.textContent = "Cancel Request";
        }
      });

      actions.appendChild(cancelBtn);
    }

    card.append(userBlock, actions);
    return card;
  }

  function checkEmptyRequests(direction) {
    const container = document.getElementById(
      direction === "incoming" ? "incoming-requests" : "outgoing-requests"
    );
    if (container && container.children.length === 0) {
      if (direction === "incoming") {
        renderEmptyState(container, "No incoming requests", "You have no pending invitations right now.", "✉️");
      } else {
        renderEmptyState(container, "No outgoing requests", "You haven't sent any pending invitations.", "📤");
      }
    }
  }

  async function loadIncoming() {
    const container = document.getElementById("incoming-requests");
    if (!container) return;
    renderLoading(container, "Loading incoming requests...");

    try {
      const data = await api("GET", "/api/v1/connections/requests/incoming");
      const items = Array.isArray(data) ? data : data?.requests || [];
      clearElement(container);

      if (items.length === 0) {
        checkEmptyRequests("incoming");
        return;
      }
      items.forEach((req) => container.appendChild(createRequestCard(req, "incoming")));
    } catch (err) {
      renderEmptyState(container, "Could not load requests", err.message, "⚠️");
    }
  }

  async function loadOutgoing() {
    const container = document.getElementById("outgoing-requests");
    if (!container) return;
    renderLoading(container, "Loading outgoing requests...");

    try {
      const data = await api("GET", "/api/v1/connections/requests/outgoing");
      const items = Array.isArray(data) ? data : data?.requests || [];
      clearElement(container);

      if (items.length === 0) {
        checkEmptyRequests("outgoing");
        return;
      }
      items.forEach((req) => container.appendChild(createRequestCard(req, "outgoing")));
    } catch (err) {
      renderEmptyState(container, "Could not load requests", err.message, "⚠️");
    }
  }

  function initRequestsPage() {
    const tabIncoming = document.getElementById("tab-incoming");
    const tabOutgoing = document.getElementById("tab-outgoing");
    const incomingBox = document.getElementById("incoming-requests");
    const outgoingBox = document.getElementById("outgoing-requests");

    if (tabIncoming && tabOutgoing && incomingBox && outgoingBox) {
      tabIncoming.addEventListener("click", () => {
        tabIncoming.classList.add("active");
        tabIncoming.setAttribute("aria-selected", "true");
        tabOutgoing.classList.remove("active");
        tabOutgoing.setAttribute("aria-selected", "false");
        incomingBox.classList.remove("hidden");
        outgoingBox.classList.add("hidden");
        loadIncoming();
      });

      tabOutgoing.addEventListener("click", () => {
        tabOutgoing.classList.add("active");
        tabOutgoing.setAttribute("aria-selected", "true");
        tabIncoming.classList.remove("active");
        tabIncoming.setAttribute("aria-selected", "false");
        outgoingBox.classList.remove("hidden");
        incomingBox.classList.add("hidden");
        loadOutgoing();
      });
    }

    loadIncoming();
  }

  /* ========================================================================
     11. Discover Page (Jaccard Recommendations)
     ======================================================================== */
  async function loadSuggestions() {
    const container =
      document.getElementById("suggestions-container") ||
      document.getElementById("suggestions-grid");
    if (!container) return;
    renderLoading(container, "Finding people you may know...");

    try {
      const data = await api("GET", "/api/v1/me/suggestions");
      const suggestions = Array.isArray(data) ? data : data?.suggestions || [];
      clearElement(container);

      if (suggestions.length === 0) {
        renderEmptyState(
          container,
          "No suggestions right now",
          "Connect with a few classmates via Search so we can recommend friends of friends.",
          "✨",
          { label: "Search Directory", href: "/search" }
        );
        return;
      }

      suggestions.forEach((item) => {
        const user = item.user || item;
        const card = document.createElement("article");
        card.className = "card card-hover suggestion-card";

        const top = document.createElement("div");
        top.className = "user-card-top";
        const displayName = user.display_name || user.username;
        const avatar = createAvatar(displayName, "avatar-md");

        const info = document.createElement("div");
        info.className = "user-card-info";

        const nameLink = document.createElement("a");
        nameLink.href = profileUrl(user.username);
        nameLink.className = "user-card-name";
        nameLink.textContent = displayName;

        const usernameEl = document.createElement("div");
        usernameEl.className = "user-card-username";
        usernameEl.textContent = `@${user.username}`;

        const metaEl = document.createElement("div");
        metaEl.className = "user-card-meta";
        const metaParts = [];
        if (user.programme) metaParts.push(user.programme);
        if (user.year) metaParts.push(`Year ${user.year}`);
        metaEl.textContent = metaParts.join(" · ") || "Campus member";

        info.append(nameLink, usernameEl, metaEl);
        top.append(avatar, info);

        const reasonBox = document.createElement("div");
        reasonBox.className = "suggestion-reason";
        reasonBox.textContent = item.reason || `${item.mutual_count || 0} mutual connections`;

        const footer = document.createElement("div");
        footer.className = "user-card-footer";

        const scoreEl = document.createElement("span");
        scoreEl.className = "suggestion-score";
        const pct = typeof item.score === "number" ? Math.round(item.score * 100) : 0;
        scoreEl.textContent = `Match: ${pct}%`;

        const connectBtn = document.createElement("button");
        connectBtn.type = "button";
        connectBtn.className = "btn btn-primary btn-sm";
        connectBtn.textContent = "Connect";

        connectBtn.addEventListener("click", async () => {
          connectBtn.disabled = true;
          connectBtn.textContent = "Sending...";
          try {
            await sendConnectionRequest(user.user_id, user.username);
            showToast(`Connection request sent to @${user.username}!`, "success");
            connectBtn.className = "btn btn-secondary btn-sm";
            connectBtn.textContent = "Request Sent";
          } catch (err) {
            showToast(err.message || "Could not send request.", "error");
            connectBtn.disabled = false;
            connectBtn.textContent = "Connect";
          }
        });

        footer.append(scoreEl, connectBtn);
        card.append(top, reasonBox, footer);
        container.appendChild(card);
      });
    } catch (err) {
      renderEmptyState(container, "Could not load suggestions", err.message, "⚠️");
    }
  }

  function initDiscoverPage() {
    loadSuggestions();
  }

  /* ========================================================================
     12. Search Page (Debounced Input + AbortController + Dropdown)
     ======================================================================== */
  async function performSearch(query) {
    const resultsContainer = document.getElementById("search-results");
    const dropdown = document.getElementById("search-dropdown");
    if (!resultsContainer) return;

    const trimmed = query.trim();
    if (!trimmed) {
      if (dropdown) {
        dropdown.classList.add("hidden");
        clearElement(dropdown);
      }
      renderEmptyState(
        resultsContainer,
        "Start typing to search",
        "Enter a username or display name above to find students across campus.",
        "🔎"
      );
      return;
    }

    if (AppState.searchAbortController) {
      AppState.searchAbortController.abort();
    }
    const controller = new AbortController();
    AppState.searchAbortController = controller;

    renderLoading(resultsContainer, `Searching for "${trimmed}"...`);

    try {
      const data = await api(
        "GET",
        `/api/v1/users/search?q=${encodeURIComponent(trimmed)}`,
        null,
        { signal: controller.signal }
      );
      const users = Array.isArray(data) ? data : data?.users || [];

      if (dropdown) {
        clearElement(dropdown);
        if (users.length > 0) {
          users.slice(0, 5).forEach((u) => {
            const item = document.createElement("a");
            item.href = profileUrl(u.username);
            item.className = "search-dropdown-item";
            item.setAttribute("role", "option");

            const av = createAvatar(u.display_name || u.username, "avatar-sm");
            const txt = document.createElement("div");
            const nm = document.createElement("div");
            nm.className = "user-card-name";
            nm.textContent = u.display_name || u.username;
            const un = document.createElement("div");
            un.className = "user-card-username";
            un.textContent = `@${u.username}`;
            txt.append(nm, un);

            item.append(av, txt);
            dropdown.appendChild(item);
          });
          dropdown.classList.remove("hidden");
        } else {
          dropdown.classList.add("hidden");
        }
      }

      clearElement(resultsContainer);
      if (users.length === 0) {
        renderEmptyState(
          resultsContainer,
          "No students found",
          `No users matched "${trimmed}". Try a shorter prefix or another name.`,
          "😕"
        );
        return;
      }

      users.forEach((user) => {
        const viewLink = document.createElement("a");
        viewLink.href = profileUrl(user.username);
        viewLink.className = "btn btn-outline btn-sm";
        viewLink.textContent = "View Profile";

        const connectBtn = document.createElement("button");
        connectBtn.type = "button";
        connectBtn.className = "btn btn-primary btn-sm";
        connectBtn.textContent = "Connect";

        if (AppState.currentUser && AppState.currentUser.id === user.user_id) {
          connectBtn.classList.add("hidden");
        } else {
          connectBtn.addEventListener("click", async () => {
            connectBtn.disabled = true;
            connectBtn.textContent = "Sending...";
            try {
              await sendConnectionRequest(user.user_id, user.username);
              showToast(`Connection request sent to @${user.username}.`, "success");
              connectBtn.className = "btn btn-secondary btn-sm";
              connectBtn.textContent = "Request Sent";
            } catch (err) {
              showToast(err.message || "Could not send request.", "error");
              connectBtn.disabled = false;
              connectBtn.textContent = "Connect";
            }
          });
        }

        resultsContainer.appendChild(createUserCard(user, [viewLink, connectBtn]));
      });
    } catch (err) {
      if (err.name === "AbortError") return;
      renderEmptyState(resultsContainer, "Search error", err.message, "⚠️");
    }
  }

  function initSearchPage() {
    const input = document.getElementById("search-input");
    const dropdown = document.getElementById("search-dropdown");
    if (!input) return;

    const debouncedSearch = debounce((val) => performSearch(val), 280);

    input.addEventListener("input", (e) => {
      debouncedSearch(e.target.value);
    });

    document.addEventListener("click", (e) => {
      if (dropdown && !e.target.closest(".search-wrapper")) {
        dropdown.classList.add("hidden");
      }
    });

    const params = new URLSearchParams(window.location.search);
    const initialQuery = params.get("q");
    if (initialQuery) {
      input.value = initialQuery;
      performSearch(initialQuery);
    }
    // Load People You May Know (mutuals, same course, shared skills) on the merged Search & Discover page
    loadSuggestions();
  }

  /* ========================================================================
     13. Notifications Page
     ======================================================================== */
  function describeNotification(notif) {
    const actorName = notif.actor?.display_name || notif.actor?.username || "Someone";
    switch (notif.type) {
      case "connection_request":
        return `${actorName} sent you a connection request.`;
      case "connection_accepted":
        return `${actorName} accepted your connection request.`;
      case "post_created":
        return `${actorName} published a new post.`;
      default:
        return `${actorName} interacted with your network (${notif.type}).`;
    }
  }

  function createNotificationItem(notif) {
    const item = document.createElement("article");
    const isUnread = !notif.read_at;
    item.className = isUnread ? "notification-item is-unread" : "notification-item";
    item.dataset.notifId = String(notif.id);
    item.tabIndex = 0;

    const content = document.createElement("div");
    content.className = "notification-content";

    const actorLabel = notif.actor?.display_name || notif.actor?.username || "CC";
    const avatar = createAvatar(actorLabel, "avatar-sm");

    const textWrap = document.createElement("div");
    const msg = document.createElement("p");
    msg.className = "notification-text";
    msg.textContent = describeNotification(notif);

    const time = document.createElement("div");
    time.className = "notification-time";
    time.textContent = formatRelativeTime(notif.created_at);

    textWrap.append(msg, time);
    content.append(avatar, textWrap);
    item.appendChild(content);

    let dot = null;
    if (isUnread) {
      dot = document.createElement("span");
      dot.className = "unread-dot";
      dot.setAttribute("aria-label", "Unread");
      item.appendChild(dot);
    }

    const markSingleRead = async () => {
      if (notif.read_at) {
        if (notif.actor?.username) {
          window.location.href = profileUrl(notif.actor.username);
        }
        return;
      }
      try {
        await api("POST", `/api/v1/notifications/${notif.id}/read`);
        notif.read_at = new Date().toISOString();
        item.classList.remove("is-unread");
        if (dot) dot.remove();
        updateNotificationBadge();
        if (notif.type === "connection_request") {
          window.location.href = "/requests";
        } else if (notif.actor?.username) {
          window.location.href = profileUrl(notif.actor.username);
        }
      } catch (err) {
        showToast(err.message || "Could not mark notification as read.", "error");
      }
    };

    item.addEventListener("click", markSingleRead);
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        markSingleRead();
      }
    });

    return item;
  }

  async function loadNotifications() {
    const list = document.getElementById("notifications-list");
    if (!list) return;
    renderLoading(list, "Loading notifications...");

    try {
      const data = await api("GET", "/api/v1/notifications");
      const notifications = Array.isArray(data) ? data : data?.notifications || [];
      clearElement(list);

      if (notifications.length === 0) {
        renderEmptyState(
          list,
          "All caught up!",
          "You don't have any notifications right now.",
          "🔔"
        );
        return;
      }

      notifications.forEach((n) => list.appendChild(createNotificationItem(n)));
    } catch (err) {
      renderEmptyState(list, "Could not load notifications", err.message, "⚠️");
    }
  }

  function initNotificationsPage() {
    loadNotifications();

    const markAllBtn = document.getElementById("mark-all-read");
    if (markAllBtn) {
      markAllBtn.addEventListener("click", async () => {
        markAllBtn.disabled = true;
        try {
          await api("POST", "/api/v1/notifications/read-all");
          document.querySelectorAll(".notification-item.is-unread").forEach((el) => {
            el.classList.remove("is-unread");
            const dot = el.querySelector(".unread-dot");
            if (dot) dot.remove();
          });
          updateNotificationBadge();
          showToast("All notifications marked as read.", "success");
        } catch (err) {
          showToast(err.message || "Failed to mark all as read.", "error");
        } finally {
          markAllBtn.disabled = false;
        }
      });
    }
  }

  /* ========================================================================
     13b. UX Micro-Features & Settings Page
     ======================================================================== */
  function initPasswordToggles() {
    document.querySelectorAll(".password-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const input = btn.previousElementSibling;
        if (!input || input.tagName !== "INPUT") return;
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        btn.setAttribute("aria-pressed", String(!showing));
        btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
        btn.textContent = showing ? "Show" : "Hide";
      });
    });
  }

  async function copyToClipboard(text, label = "Text") {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
      showToast(`${label} copied to clipboard.`, "success");
    } catch (_) {
      showToast(`Could not copy ${label.toLowerCase()}.`, "error");
    }
  }

  function showConfirmModal({ title, message, confirmLabel = "Confirm" }) {
    return new Promise((resolve) => {
      const prevFocus = document.activeElement;
      const backdrop = document.createElement("div");
      backdrop.className = "modal-backdrop";
      backdrop.setAttribute("role", "dialog");
      backdrop.setAttribute("aria-modal", "true");
      backdrop.setAttribute("aria-labelledby", "confirm-modal-title");

      const box = document.createElement("div");
      box.className = "card modal-box";
      const h2 = document.createElement("h2");
      h2.id = "confirm-modal-title";
      h2.className = "section-heading";
      h2.textContent = title;
      const p = document.createElement("p");
      p.textContent = message;

      const actions = document.createElement("div");
      actions.className = "profile-actions";
      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.className = "btn btn-outline btn-sm";
      cancelBtn.textContent = "Cancel";
      const okBtn = document.createElement("button");
      okBtn.type = "button";
      okBtn.className = "btn btn-outline-danger btn-sm";
      okBtn.textContent = confirmLabel;

      const close = (result) => {
        document.removeEventListener("keydown", onKey);
        backdrop.remove();
        if (prevFocus && typeof prevFocus.focus === "function") prevFocus.focus();
        resolve(result);
      };
      const onKey = (e) => {
        if (e.key === "Escape") close(false);
      };

      cancelBtn.addEventListener("click", () => close(false));
      okBtn.addEventListener("click", () => close(true));
      document.addEventListener("keydown", onKey);

      actions.append(cancelBtn, okBtn);
      box.append(h2, p, actions);
      backdrop.appendChild(box);
      document.body.appendChild(backdrop);
      cancelBtn.focus();
    });
  }

  function initCookieConsentAndUtm() {
    const CONSENT_KEY = "cc-consent-v1.3";
    const captureUtmIfAllowed = (consent) => {
      if (!consent?.analytics) return;
      if (localStorage.getItem("cc-utm-first-touch")) return;
      const params = new URLSearchParams(window.location.search);
      const allow = ["utm_source", "utm_medium", "utm_campaign", "utm_content"];
      const utm = {};
      allow.forEach((k) => {
        const v = params.get(k);
        if (v) utm[k] = v.trim().slice(0, 64);
      });
      if (Object.keys(utm).length > 0) {
        localStorage.setItem("cc-utm-first-touch", JSON.stringify({ ...utm, ts: Date.now() }));
      }
    };

    const existingRaw = localStorage.getItem(CONSENT_KEY);
    if (existingRaw) {
      try {
        captureUtmIfAllowed(JSON.parse(existingRaw));
        return;
      } catch (_) {}
    }

    const banner = document.createElement("aside");
    banner.id = "cookie-banner";
    banner.className = "cookie-banner";
    banner.setAttribute("aria-label", "Cookie preferences");

    const text = document.createElement("p");
    text.textContent = "CampusHive uses essential cookies for sign-in and security. Optional analytics is off unless you accept.";
    const btns = document.createElement("div");
    btns.className = "profile-actions";

    const saveChoice = (analytics) => {
      const choice = { version: "1.3", essential: true, analytics, ts: new Date().toISOString() };
      localStorage.setItem(CONSENT_KEY, JSON.stringify(choice));
      captureUtmIfAllowed(choice);
      if (AppState.currentUser) {
        api("POST", "/api/v1/me/consent", { policy_version: "1.3", analytics_allowed: analytics }).catch(() => {});
      }
      banner.remove();
    };

    const acceptBtn = document.createElement("button");
    acceptBtn.type = "button";
    acceptBtn.className = "btn btn-primary btn-sm";
    acceptBtn.textContent = "Accept optional";
    acceptBtn.addEventListener("click", () => saveChoice(true));

    const rejectBtn = document.createElement("button");
    rejectBtn.type = "button";
    rejectBtn.className = "btn btn-outline btn-sm";
    rejectBtn.textContent = "Reject optional";
    rejectBtn.addEventListener("click", () => saveChoice(false));

    btns.append(acceptBtn, rejectBtn);
    banner.append(text, btns);
    document.body.appendChild(banner);
  }

  function initQuickSearch() {
    const openQuickSearch = () => {
      if (!AppState.currentUser) return;
      if (document.getElementById("quick-search-modal")) return;
      const backdrop = document.createElement("div");
      backdrop.id = "quick-search-modal";
      backdrop.className = "modal-backdrop";
      backdrop.setAttribute("role", "dialog");
      backdrop.setAttribute("aria-modal", "true");
      backdrop.setAttribute("aria-label", "Quick student search");

      const box = document.createElement("div");
      box.className = "card modal-box";
      const input = document.createElement("input");
      input.type = "search";
      input.className = "form-input";
      input.placeholder = "Search students by name or username...";
      input.setAttribute("aria-label", "Search students");
      const resultsEl = document.createElement("div");
      resultsEl.className = "quick-search-results";

      const close = () => {
        document.removeEventListener("keydown", onKey);
        backdrop.remove();
      };
      const onKey = (e) => {
        if (e.key === "Escape") close();
      };
      document.addEventListener("keydown", onKey);
      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) close();
      });

      input.addEventListener("input", debounce(async () => {
        const q = input.value.trim();
        clearElement(resultsEl);
        if (!q) return;
        try {
          const res = await api("GET", `/api/v1/users/search?q=${encodeURIComponent(q)}&limit=6`);
          (res.users || []).forEach((u) => {
            const a = document.createElement("a");
            a.href = profileUrl(u.username);
            a.className = "quick-search-item";
            a.textContent = `${u.display_name || u.username} (@${u.username})`;
            resultsEl.appendChild(a);
          });
        } catch (_) {}
      }, 200));

      box.append(input, resultsEl);
      backdrop.appendChild(box);
      document.body.appendChild(backdrop);
      input.focus();
    };

    const trigger = document.getElementById("quick-search-trigger");
    if (trigger) trigger.addEventListener("click", openQuickSearch);

    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openQuickSearch();
      }
    });
  }

  function initScrollControls() {
    const bar = document.createElement("div");
    bar.className = "scroll-progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.appendChild(bar);

    const topBtn = document.createElement("button");
    topBtn.type = "button";
    topBtn.className = "back-to-top hidden";
    topBtn.setAttribute("aria-label", "Back to top");
    topBtn.textContent = "↑ Top";
    topBtn.addEventListener("click", () => {
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
    });
    document.body.appendChild(topBtn);

    const helpLink = document.createElement("a");
    helpLink.href = "/help";
    helpLink.className = "floating-help-btn";
    helpLink.setAttribute("aria-label", "Help and Support");
    helpLink.textContent = "? Help";
    document.body.appendChild(helpLink);

    window.addEventListener("scroll", () => {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const docHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const pct = docHeight > 0 ? Math.min(100, Math.round((scrollTop / docHeight) * 100)) : 0;
      bar.style.width = `${pct}%`;
      topBtn.classList.toggle("hidden", scrollTop < 360);
    }, { passive: true });
  }

  async function initSettingsPage() {
    const pwForm = document.getElementById("change-password-form");
    const errBox = document.getElementById("change-pw-error");
    const okBox = document.getElementById("change-pw-success");
    if (pwForm) {
      pwForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (errBox) errBox.textContent = "";
        if (okBox) {
          okBox.textContent = "";
          okBox.classList.add("hidden");
        }
        const cur = document.getElementById("current-password")?.value || "";
        const nw = document.getElementById("new-password")?.value || "";
        const cfm = document.getElementById("confirm-new-password")?.value || "";
        const pwErr = validatePasswordPolicyClient(nw);
        if (pwErr) {
          if (errBox) errBox.textContent = pwErr;
          return;
        }
        if (nw !== cfm) {
          if (errBox) errBox.textContent = "New passwords do not match.";
          return;
        }
        try {
          await api("POST", "/api/v1/me/password", { current_password: cur, new_password: nw });
          pwForm.reset();
          if (okBox) {
            okBox.textContent = "Password updated. Other active sessions have been signed out.";
            okBox.classList.remove("hidden");
          }
          await loadSessionsList();
        } catch (err) {
          if (errBox) errBox.textContent = err.message || "Could not update password.";
        }
      });
    }

    async function loadSessionsList() {
      const list = document.getElementById("sessions-list");
      if (!list) return;
      clearElement(list);
      try {
        const sessions = await api("GET", "/api/v1/me/sessions");
        sessions.forEach((s) => {
          const row = document.createElement("div");
          row.className = "session-row";
          const info = document.createElement("span");
          info.textContent = `Session #${s.id} · Created ${formatRelativeTime(s.created_at)}${s.is_current ? " (Current)" : ""}`;
          row.appendChild(info);
          if (!s.is_current) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn btn-outline-danger btn-sm";
            btn.textContent = "Revoke";
            btn.addEventListener("click", async () => {
              await api("DELETE", `/api/v1/me/sessions/${s.id}`);
              showToast("Session revoked.", "info");
              await loadSessionsList();
            });
            row.appendChild(btn);
          }
          list.appendChild(row);
        });
      } catch (err) {
        list.textContent = err.message || "Could not load sessions.";
      }
    }
    await loadSessionsList();

    const themeSelect = document.getElementById("pref-theme");
    const motionCheck = document.getElementById("pref-reduced-motion");
    const savePrefsBtn = document.getElementById("save-prefs-btn");
    try {
      const prefs = await api("GET", "/api/v1/me/preferences");
      if (themeSelect && prefs.theme) themeSelect.value = prefs.theme;
      if (motionCheck) motionCheck.checked = Boolean(prefs.reduced_motion);
    } catch (_) {}

    if (savePrefsBtn) {
      savePrefsBtn.addEventListener("click", async () => {
        const theme = themeSelect?.value || "system";
        const reduced_motion = Boolean(motionCheck?.checked);
        await api("PATCH", "/api/v1/me/preferences", { theme, reduced_motion });
        if (theme === "system") {
          document.documentElement.removeAttribute("data-theme");
          localStorage.removeItem("cc-theme");
        } else {
          document.documentElement.setAttribute("data-theme", theme);
          localStorage.setItem("cc-theme", theme);
        }
        showToast("Preferences saved.", "success");
      });
    }

    const cookieBtn = document.getElementById("open-cookie-prefs-btn");
    if (cookieBtn) {
      cookieBtn.addEventListener("click", () => {
        localStorage.removeItem("cc-consent-v1.3");
        initCookieConsentAndUtm();
      });
    }
  }

  /* ========================================================================
     14. Application Bootstrap
     ======================================================================== */
  document.addEventListener("DOMContentLoaded", async () => {
    initTheme();
    setupNav();
    initPasswordToggles();
    initScrollControls();
    initCookieConsentAndUtm();
    initQuickSearch();

    const page = getCurrentPage();
    const user = await checkAuth(page);

    if (user) {
      updateNavBar(user);
      updateNotificationBadge();
    }

    switch (page) {
      case "login":
        initLoginPage();
        break;
      case "register":
        initRegisterPage();
        break;
      case "home":
        initHomePage();
        break;
      case "profile":
        initProfilePage();
        break;
      case "my_profile":
        initMyProfilePage();
        break;
      case "connections":
        initConnectionsPage();
        break;
      case "requests":
        initRequestsPage();
        break;
      case "discover":
        initDiscoverPage();
        break;
      case "groups":
        initGroupsPage();
        break;
      case "settings":
        initSettingsPage();
        break;
      case "search":
        initSearchPage();
        break;
      case "notifications":
        initNotificationsPage();
        break;
      case "landing":
      default:
        break;
    }
  });
})();
