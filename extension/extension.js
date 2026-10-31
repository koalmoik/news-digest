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

// Tage in Folge mit gelesenem Digest; ein noch offener heutiger Digest unterbricht die Serie nicht
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
    try {
        Gio.AppInfo.launch_default_for_uri(uri, global.create_app_launch_context(0, -1));
    } catch (e) {
        logError(e, 'news-digest');
    }
}

// Mehrzeiliger Text mit fester Breite
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
        super._init(0.5, 'Morgen-Digest');
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
        // Alle 5 Minuten prüfen, ob der Digest von gestern ist (Tageswechsel)
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
            Main.notify('Fertig für heute ✓', n > 1 ? `🔥 ${n} Tage in Folge informiert` : 'Gut gemacht!');
            this._streakLabel.text = this._streakText();
        }
        this._saveState();
        this._updateLabel();
    }

    _streakText() {
        const n = streakOf(this._state.done);
        return n ? `🔥 Serie: ${n} ${n === 1 ? 'Tag' : 'Tage'}` : 'Lies alle Meldungen, um eine Serie zu starten';
    }

    _buildMenu() {
        this._shownDay = isoDay();
        this.menu.removeAll();
        const d = this._digest;
        if (!d) {
            this.menu.addMenuItem(new PopupMenu.PopupMenuItem('Noch kein Digest – kommt um 6:30', {reactive: false}));
        } else {
            this.menu.addMenuItem(textItem(wrappedLabel(d.title, 'font-weight: bold;')));
            if (d.date !== isoDay()) {
                this.menu.addMenuItem(textItem(wrappedLabel('Der heutige Digest ist noch nicht da – ' +
                    'das ist der letzte verfügbare.', 'color: #e5a50a;')));
            }
            this.menu.addMenuItem(textItem(wrappedLabel(d.intro, 'font-style: italic;')));
            this._streakLabel = wrappedLabel(this._streakText(), 'color: #ff7800;');
            this.menu.addMenuItem(textItem(this._streakLabel));

            // Die Meldungen scrollen, damit das Menü nicht über den Bildschirm hinausragt
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
                    // Lange Titel umbrechen statt abschneiden
                    sub.label.set_style(`width: ${TEXT_WIDTH};`);
                    sub.label.clutter_text.line_wrap = true;
                    sub.label.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
                    sub.label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
                    sub.setOrnament(readIds.includes(it.id) ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.DOT);
                    sub.menu.addMenuItem(textItem(wrappedLabel(it.summary)));
                    for (const s of it.sources) {
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
            this.menu.addAction('Alle als gelesen markieren', () => {
                for (const it of this._allItems())
                    this._markRead(it, {setOrnament: () => {}});
                this._buildMenu();
            }, 'object-select-symbolic');
            this.menu.addAction('Im Browser lesen', () =>
                openUri(`${PAGES_URL}/${d.date}.html`), 'web-browser-symbolic');
        }
        this.menu.addAction('Jetzt aktualisieren', () => {
            try {
                Gio.Subprocess.new([SYNC], Gio.SubprocessFlags.NONE);
            } catch (e) {
                logError(e, 'news-digest');
            }
        }, 'view-refresh-symbolic');
    }

    // Aufgeklappte Meldung ganz sichtbar machen, sobald die Aufklapp-Animation fertig ist
    _scrollIntoView(scroll, sub) {
        if (this._scrollTimer)
            GLib.source_remove(this._scrollTimer);
        this._scrollTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, () => {
            this._scrollTimer = 0;
            ensureActorVisibleInScrollView(scroll, sub.menu.actor);
            // danach den Titel, falls die Zusammenfassung höher als der sichtbare Bereich ist
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
        // Links in der Leiste, gleich nach „Aktivitäten“
        Main.panel.addToStatusArea(this.uuid, this._indicator, 1, 'left');
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
