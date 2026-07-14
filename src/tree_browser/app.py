"""A compact Qt WebEngine browser with tabs represented as a tree."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
)

from .address import HOME_URL, normalise_address


@dataclass
class Tab:
    """The browser view associated with one item in the tab tree."""

    view: QWebEngineView


class TabWebView(QWebEngineView):
    """A page view that asks its owning tree node to create child tabs."""

    def __init__(self, open_child: Callable[[], QWebEngineView]) -> None:
        super().__init__()
        self._open_child = open_child

    def createWindow(self, _window_type: object) -> QWebEngineView:
        """Keep browser-created pages under the tab that opened them.

        Qt WebEngine calls this for link context-menu actions, Ctrl+click,
        middle-click, target=_blank links, and JavaScript popup requests.
        """
        return self._open_child()


class BrowserWindow(QMainWindow):
    """Main window that keeps a web view for every node in a tab tree."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tree Browser")
        self.resize(1200, 760)
        self._tabs: dict[QTreeWidgetItem, Tab] = {}

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Tabs")
        self.tree.setMinimumWidth(220)
        self.tree.currentItemChanged.connect(self._select_tab)

        self.pages = QStackedWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.address = QLineEdit()
        self.address.setPlaceholderText("Enter a URL or search term")
        self.address.returnPressed.connect(self.navigate)
        self._build_toolbar()
        self.new_tab()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, callback in (("←", self.go_back), ("→", self.go_forward), ("⟳", self.reload)):
            button = QPushButton(text)
            button.setFixedWidth(34)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addWidget(self.address)
        go = QPushButton("Go")
        go.clicked.connect(self.navigate)
        toolbar.addWidget(go)
        toolbar.addAction(self._action("New tab", "Ctrl+T", self.new_tab))
        toolbar.addAction(self._action("New child", "Ctrl+Shift+T", self.new_child_tab))
        toolbar.addAction(self._action("Close", "Ctrl+W", self.close_tab))

    def _action(self, label: str, shortcut: str, callback: object) -> QAction:
        action = QAction(label, self)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)  # type: ignore[arg-type]
        return action

    def _make_tab(self, parent: QTreeWidgetItem | None = None, *, load_home: bool = True) -> QTreeWidgetItem:
        item = QTreeWidgetItem(["New tab"])
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
            parent.setExpanded(True)
        view = TabWebView(lambda node=item: self._open_child_for(node))
        self._tabs[item] = Tab(view)
        self.pages.addWidget(view)
        view.titleChanged.connect(lambda title, node=item: self._set_title(node, title))
        view.urlChanged.connect(lambda url, node=item: self._set_url(node, url))
        self.tree.setCurrentItem(item)
        if load_home:
            view.setUrl(QUrl(HOME_URL))
        return item

    def _open_child_for(self, parent: QTreeWidgetItem) -> QWebEngineView:
        """Create an empty child view for Qt WebEngine to load into."""
        item = self._make_tab(parent, load_home=False)
        return self._tabs[item].view

    def new_tab(self) -> None:
        self._make_tab()

    def new_child_tab(self) -> None:
        self._make_tab(self.tree.currentItem())

    def close_tab(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        parent = item.parent()
        next_item = self._adjacent_item(item) or parent
        self._remove_item(item)
        if next_item is None and not self._tabs:
            self.new_tab()
        elif next_item is not None:
            self.tree.setCurrentItem(next_item)

    def _adjacent_item(self, item: QTreeWidgetItem) -> QTreeWidgetItem | None:
        """Return a sibling to select after a tab is closed, if one exists."""
        parent = item.parent()
        siblings = (
            [parent.child(index) for index in range(parent.childCount())]
            if parent is not None
            else [self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())]
        )
        index = siblings.index(item)
        return siblings[index + 1] if index + 1 < len(siblings) else (siblings[index - 1] if index else None)

    def _remove_item(self, item: QTreeWidgetItem) -> None:
        for index in range(item.childCount() - 1, -1, -1):
            self._remove_item(item.child(index))
        tab = self._tabs.pop(item)
        self.pages.removeWidget(tab.view)
        tab.view.deleteLater()
        if item.parent() is None:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        else:
            item.parent().removeChild(item)

    def _select_tab(self, item: QTreeWidgetItem | None, _: QTreeWidgetItem | None) -> None:
        if item is None or item not in self._tabs:
            return
        view = self._tabs[item].view
        self.pages.setCurrentWidget(view)
        self.address.setText(view.url().toString())
        view.setFocus()

    def _set_title(self, item: QTreeWidgetItem, title: str) -> None:
        item.setText(0, title or "New tab")

    def _set_url(self, item: QTreeWidgetItem, url: QUrl) -> None:
        if item is self.tree.currentItem():
            self.address.setText(url.toString())

    def _current_view(self) -> QWebEngineView | None:
        item = self.tree.currentItem()
        return self._tabs[item].view if item in self._tabs else None

    def navigate(self) -> None:
        view = self._current_view()
        if view is not None:
            view.setUrl(QUrl.fromUserInput(normalise_address(self.address.text())))

    def go_back(self) -> None:
        if view := self._current_view():
            view.back()

    def go_forward(self) -> None:
        if view := self._current_view():
            view.forward()

    def reload(self) -> None:
        if view := self._current_view():
            view.reload()


def main() -> int:
    app = QApplication(sys.argv)
    window = BrowserWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
