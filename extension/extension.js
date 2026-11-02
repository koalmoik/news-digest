import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Pango from 'gi://Pango';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {ensureActorVisibleInScrollView} from 'resource:///org/gnome/shell/misc/animationUtils.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const CACHE_DIR = GLib.build_filenamev([GLib.get_user_cache_dir(), 'news-digest']);
const DIGEST_FILE = GLib.build_filenamev([CACHE_DIR, 'latest.json']);
const STATE_DIR = GLib.build_filenamev([GLib.get_user_state_dir(), 'news-digest']);
const STATE_FILE = GLib.build_filenamev([STATE_DIR, 'state.json']);
const CONFIG_FILE = GLib.build_filenamev([GLib.get_user_config_dir(), 'news-digest', 'config.json']);
const SYNC = GLib.build_filenamev([GLib.get_home_dir(), 'Programs', 'news-digest', 'sync.sh']);
const PAGES_URL = 'https://koalmoik.github.io/news-digest-pages';
const KEEP_DAYS = 14;
const ACCENT = '#62a0ea';
const TEXT_WIDTH = '28em';

function isoDay(offset = 0) {
    const d = new Date();
    d.setDate(d.getDate() + offset);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function readJson(path, fallback) {
    try {
        const [, bytes] = GLib.file_get_contents(path);
        return JSON.parse(new TextDecoder().decode(bytes));
    } catch {
        return fallback;
    }
}

// UI language: "language" in ~/.config/news-digest/config.json, otherwise the system locale.
// The digest itself is always written in German.
const LANG = (() => {
    const lang = readJson(CONFIG_FILE, {})?.language;
    if (lang === 'en' || lang === 'de')
        return lang;
    return GLib.get_language_names()[0].toLowerCase().startsWith('de') ? 'de' : 'en';
})();

const DE = {
    'Morning digest': 'Morgen-Digest',
    'Done for today ✓': 'Fertig für heute ✓',
    '🔥 {n} days in a row informed': '🔥 {n} Tage in Folge informiert',
    'Well done!': 'Gut gemacht!',
    '🔥 Streak: 1 day': '🔥 Serie: 1 Tag',
    '🔥 Streak: {n} days': '🔥 Serie: {n} Tage',
    'Read all items to start a streak': 'Lies alle Meldungen, um eine Serie zu starten',
    'No digest yet – it arrives around 6:30': 'Noch kein Digest – kommt um 6:30',
    'Today’s digest isn’t here yet – this is the latest one available.':
        'Der heutige Digest ist noch nicht da – das ist der letzte verfügbare.',
    'Mark all as read': 'Alle als gelesen markieren',
    'Read in browser': 'Im Browser lesen',
    'Refresh now': 'Jetzt aktualisieren',
};

function _(text, n) {
    const out = LANG === 'de' ? DE[text] ?? text : text;
    return n === undefined ? out : out.replace('{n}', n);
}

// Links come from third-party RSS feeds: only ever open plain web links
function isWebUrl(url) {
    return typeof url === 'string' && /^https?:\/\//i.test(url);
}

// Consecutive days with a fully read digest; today's digest still being open does not break the streak
function streakOf(done) {
    const days = new Set(done);
    let offset = days.has(isoDay()) ? 0 : -1;
    let n = 0;
    while (days.has(isoDay(offset))) {
        n++;
        offset--;
    }
    return n;
}

function openUri(uri) {
    if (!isWebUrl(uri)) {
        log(`news-digest: refusing to open non-web link ${uri}`);
        return;
    }
    try {
        Gio.AppInfo.launch_default_for_uri(uri, global.create_app_launch_context(0, -1));
    } catch (e) {
        logError(e, 'news-digest');
    }
}

// Multi-line text with a fixed width
function wrappedLabel(text, style = '') {
    const label = new St.Label({text, style: `width: ${TEXT_WIDTH}; ${style}`});
    label.clutter_text.line_wrap = true;
    label.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
    label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
    return label;
}

function textItem(label) {
    const item = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
    item.add_child(label);
    return item;
}

const DigestIndicator = GObject.registerClass(
class DigestIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.5, _('Morning digest'));
        const box = new St.BoxLayout({style_class: 'panel-status-menu-box'});
        box.add_child(new St.Icon({icon_name: 'emblem-documents-symbolic', style_class: 'system-status-icon'}));
        this._label = new St.Label({text: '…', y_align: Clutter.ActorAlign.CENTER});
        box.add_child(this._label);
        this.add_child(box);

        GLib.mkdir_with_parents(CACHE_DIR, 0o700);
        GLib.mkdir_with_parents(STATE_DIR, 0o700);
        this._state = readJson(STATE_FILE, {});
        this._state.read ??= {};
        this._state.done ??= [];

        this._monitor = Gio.File.new_for_path(CACHE_DIR)
            .monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, null);
        this._monitor.connect('changed', (_m, file, other) => {
            if ([file, other].some(f => f?.get_basename() === 'latest.json'))
                this._reload();
        });
        // Check every 5 minutes whether the digest is from yesterday (day change)
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 300, () => {
            this._reload();
            return GLib.SOURCE_CONTINUE;
        });
        this._reload();
    }

    _saveState() {
        const cutoff = isoDay(-KEEP_DAYS);
        for (const day of Object.keys(this._state.read)) {
            if (day < cutoff)
                delete this._state.read[day];
        }
        try {
            GLib.file_set_contents(STATE_FILE, JSON.stringify(this._state));
        } catch (e) {
            logError(e, 'news-digest');
        }
    }

    _readIds() {
        return this._state.read[this._digest?.date] ?? [];
    }

    _allItems() {
        return (this._digest?.topics ?? []).flatMap(t => t.items);
    }

    _reload() {
        const digest = readJson(DIGEST_FILE, null);
        const changed = JSON.stringify(digest) !== JSON.stringify(this._digest);
        this._digest = digest;
        if (digest && digest.date === isoDay() && this._state.notified !== digest.date) {
            this._state.notified = digest.date;
            this._saveState();
            Main.notify(digest.title, digest.intro);
        }
        this._updateLabel();
        if (changed || this._shownDay !== isoDay())
            this._buildMenu();
    }

    _updateLabel() {
        if (!this._digest) {
            this._label.text = ' ?';
            this._label.set_style(null);
            return;
        }
        const unread = this._allItems().length - this._readIds().length;
        const fresh = this._digest.date === isoDay();
        this._label.text = unread > 0 ? ` ${unread}` : ' ✓';
        this._label.set_style(unread > 0 && fresh ? `color: ${ACCENT}; font-weight: bold;` : null);
    }

    _markRead(item, ornamentItem) {
        const ids = this._readIds();
        if (ids.includes(item.id))
            return;
        this._state.read[this._digest.date] = [...ids, item.id];
        ornamentItem.setOrnament(PopupMenu.Ornament.CHECK);
        const allRead = this._allItems().every(i => this._state.read[this._digest.date].includes(i.id));
        if (allRead && this._digest.date === isoDay() && !this._state.done.includes(isoDay())) {
            this._state.done.push(isoDay());
            const n = streakOf(this._state.done);
            Main.notify(_('Done for today ✓'), n > 1 ? _('🔥 {n} days in a row informed', n) : _('Well done!'));
            this._streakLabel.text = this._streakText();
        }
        this._saveState();
        this._updateLabel();
    }

    _streakText() {
        const n = streakOf(this._state.done);
        if (!n)
            return _('Read all items to start a streak');
        return n === 1 ? _('🔥 Streak: 1 day') : _('🔥 Streak: {n} days', n);
    }

    _buildMenu() {
        this._shownDay = isoDay();
        this.menu.removeAll();
        const d = this._digest;
        if (!d) {
            this.menu.addMenuItem(new PopupMenu.PopupMenuItem(_('No digest yet – it arrives around 6:30'), {reactive: false}));
        } else {
            this.menu.addMenuItem(textItem(wrappedLabel(d.title, 'font-weight: bold;')));
            if (d.date !== isoDay()) {
                this.menu.addMenuItem(textItem(wrappedLabel(
                    _('Today’s digest isn’t here yet – this is the latest one available.'),
                    'color: #e5a50a;')));
            }
            this.menu.addMenuItem(textItem(wrappedLabel(d.intro, 'font-style: italic;')));
            this._streakLabel = wrappedLabel(this._streakText(), 'color: #ff7800;');
            this.menu.addMenuItem(textItem(this._streakLabel));

            // Scroll the items so the menu does not run off the screen
            const holder = new PopupMenu.PopupMenuSection();
            const section = new PopupMenu.PopupMenuSection();
            this.menu.addMenuItem(holder);
            holder.addMenuItem(section);
            holder.actor.remove_child(section.actor);
            const scroll = new St.ScrollView({
                child: section.actor, style: 'max-height: 55em;',
                hscrollbar_policy: St.PolicyType.NEVER, vscrollbar_policy: St.PolicyType.AUTOMATIC,
            });
            holder.actor.add_child(scroll);

            const readIds = this._readIds();
            for (const topic of d.topics) {
                section.addMenuItem(new PopupMenu.PopupSeparatorMenuItem(topic.name));
                for (const it of topic.items) {
                    const sub = new PopupMenu.PopupSubMenuMenuItem(it.title);
                    // Wrap long titles instead of cutting them off
                    sub.label.set_style(`width: ${TEXT_WIDTH};`);
                    sub.label.clutter_text.line_wrap = true;
                    sub.label.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
                    sub.label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
                    sub.setOrnament(readIds.includes(it.id) ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.DOT);
                    sub.menu.addMenuItem(textItem(wrappedLabel(it.summary)));
                    for (const s of it.sources.filter(src => isWebUrl(src.url))) {
                        sub.menu.addAction(`${s.name}${s.paywall ? ' 🔒' : ''}  ↗`,
                            () => openUri(s.url), 'web-browser-symbolic');
                    }
                    sub.menu.connect('open-state-changed', (_m, open) => {
                        if (!open)
                            return;
                        this._markRead(it, sub);
                        this._scrollIntoView(scroll, sub);
                    });
                    section.addMenuItem(sub);
                }
            }
        }
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        if (d) {
            this.menu.addAction(_('Mark all as read'), () => {
                for (const it of this._allItems())
                    this._markRead(it, {setOrnament: () => {}});
                this._buildMenu();
            }, 'object-select-symbolic');
            this.menu.addAction(_('Read in browser'), () =>
                openUri(`${PAGES_URL}/${d.date}.html`), 'web-browser-symbolic');
        }
        this.menu.addAction(_('Refresh now'), () => {
            try {
                Gio.Subprocess.new([SYNC], Gio.SubprocessFlags.NONE);
            } catch (e) {
                logError(e, 'news-digest');
            }
        }, 'view-refresh-symbolic');
    }

    // Scroll an expanded item fully into view once the expand animation has finished
    _scrollIntoView(scroll, sub) {
        if (this._scrollTimer)
            GLib.source_remove(this._scrollTimer);
        this._scrollTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, () => {
            this._scrollTimer = 0;
            ensureActorVisibleInScrollView(scroll, sub.menu.actor);
            // then the title, in case the summary is taller than the visible area
            ensureActorVisibleInScrollView(scroll, sub);
            return GLib.SOURCE_REMOVE;
        });
    }

    destroy() {
        for (const id of [this._timer, this._scrollTimer]) {
            if (id)
                GLib.source_remove(id);
        }
        this._timer = this._scrollTimer = 0;
        this._monitor?.cancel();
        super.destroy();
    }
});

export default class NewsDigestExtension extends Extension {
    enable() {
        this._indicator = new DigestIndicator();
        // Left side of the panel, right after “Activities”
        Main.panel.addToStatusArea(this.uuid, this._indicator, 1, 'left');
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
