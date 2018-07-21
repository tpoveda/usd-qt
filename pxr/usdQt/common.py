#
# Copyright 2017 Luma Pictures
#
# Licensed under the Apache License, Version 2.0 (the "Apache License")
# with the following modification you may not use this file except in
# compliance with the Apache License and the following modification to it:
# Section 6. Trademarks. is deleted and replaced with:
#
# 6. Trademarks. This License does not grant permission to use the trade
#    names, trademarks, service marks, or product names of the Licensor
#    and its affiliates, except as required to comply with Section 4(c) of
#    the License and to reproduce the content of the NOTICE file.
#
# You may obtain a copy of the Apache License at
#
#     http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Apache License with the above modification is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the Apache License for the specific
# language governing permissions and limitations under the Apache License.
#

from functools import partial

from pxr import Sdf

from ._Qt import QtCore, QtGui, QtWidgets

if False:
    from typing import *

NULL_INDEX = QtCore.QModelIndex()

NO_COLOR = QtGui.QColor(0, 0, 0, 0)
GREEN = QtGui.QColor(14, 93, 45, 200)
BRIGHT_GREEN = QtGui.QColor(14, 163, 45, 200)
YELLOW = QtGui.QColor(255, 255, 102, 200)
BRIGHT_YELLOW = QtGui.QColor(255, 255, 185, 200)
DARK_ORANGE = QtGui.QColor(186, 99, 0, 200)
LIGHT_BLUE = QtGui.QColor(78, 181, 224, 200)
BRIGHT_ORANGE = QtGui.QColor(255, 157, 45, 200)
PALE_ORANGE = QtGui.QColor(224, 150, 66, 200)
DARK_BLUE = QtGui.QColor(14, 82, 130, 200)


class FallbackException(Exception):
    '''Raised if a customized function fails and wants to fallback to the
    default implementation.'''
    pass


def BlendColors(color1, color2, mix=.5):
    return QtGui.QColor(*[one * mix + two * (1 - mix)
                          for one, two in
                          zip(color1.getRgb(), color2.getRgb())])


def CopyToClipboard(text):
    cb = QtWidgets.QApplication.clipboard()
    cb.setText(text, QtGui.QClipboard.Selection)
    cb.setText(text, QtGui.QClipboard.Clipboard)


class _MenuSeparator(object):
    '''Use with Actions to specify a separator when configuring menu actions'''
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
        return cls._instance

    def __call__(self, *args, **kwargs):
        return self

    def AddToMenu(self, menu, context):
        a = menu.addSeparator()
        a.setData(self)


MenuSeparator = _MenuSeparator()


# TODO: How to persist calculated values from context across methods?
# TODO: Decorator to wrap function as simple MenuAction?
class MenuAction(object):
    '''Base class for menu actions'''
    __slots__ = ('_callable',)

    def __init__(self, func=None):
        self._callable = func

    def do(self, context):
        # type: (Context) -> None
        '''Called when the action is triggered.

        Parameters
        ----------
        context : Context
        '''
        if self._callable:
            self._callable()
        else:
            raise NotImplementedError(
                'No callable provided and do() method not reimplemented by '
                'class %s' % self.__class__.__name__)

    def enable(self, context):
        # type: (Context) -> bool
        '''Return whether the menu item should be enabled.

        Parameters
        ----------
        context : Context

        Returns
        -------
        bool
        '''
        return True

    def label(self, context):
        # type: (Context) -> str
        '''Return a label for the menu item.

        Parameters
        ----------
        context : Context

        Returns
        -------
        str
        '''
        raise NotImplementedError

    def Build(self, context):
        '''Create and return a `QAction` to add to a menu that is being built.

        This can be overridden to implement things like dynamic submenus. It is
        also valid to return None to avoid adding an action to the menu.

        Parameters
        ----------
        context : Context

        Returns
        -------
        Optional[QAction]
        '''
        action = QtWidgets.QAction(self.label(context), None)
        if self.enable(context):
            action.triggered.connect(lambda: self.do(context))
        else:
            action.setEnabled(False)
        return action

    def AddToMenu(self, menu, context):
        '''Add this action to a `QMenu` that is being built.

        This calls `self.Build()` to create a `QAction`, and if the result is
        not None, adds it to the given menu and attaches this `MenuAction`
        instance to it as custom data.

        This is the preferred method for adding `MenuAction` instances to menus.

        Parameters
        ----------
        menu : QtWidgets.QMenu
        context : Context
        '''
        action = self.Build(context)
        if action is not None:
            action.setData(self)
            menu.addAction(action)
            action.setParent(menu)

    def Update(self, action, context):
        '''Update an existing `QAction` that was generated by this `MenuAction`
        instance.

        This method may be called by the owner of a persistent menu before it is
        shown. It can be used to update things like the enabled state, text, or
        even visibility of the given action.

        The default implementation updates the enabled state based on the result
        of `self.enable(context)`.

        Parameters
        ----------
        action : QtWidgets.QAction
        context : Context
        '''
        action.setEnabled(self.enable(context))


class MenuBuilder(object):
    '''Container class for a menu definition.'''
    __slots__ = ('name', 'actions')

    def __init__(self, name, actions):
        '''
        Parameters
        ----------
        name : str
        actions : List[MenuAction]
        '''
        name = name.strip()
        assert name
        self.name = name
        # TODO: Support MenuAction classes or instances
        self.actions = actions

    def Build(self, context, parent=None):
        '''Build and return a new `QMenu` instance using the current list of
        actions and the given context, and parented to the given Qt parent.

        Returns None if the resulting menu is empty.

        Parameters
        ----------
        context : Context
        parent : Optional[QtWidgets.QWidget]

        Returns
        -------
        Optional[QtWidgets.QMenu]
        '''
        menu = QtWidgets.QMenu(self.name, parent)
        for action in self.actions:
            action.AddToMenu(menu, context)
        if not menu.isEmpty():
            return menu


# TODO: Is contextMenuBuilder arg necessary at this point?
class ContextMenuMixin(object):
    '''Mix this class in with a widget to bind a context menu to it.'''
    def __init__(self, contextMenuActions=None, parent=None):
        '''
        Parameters
        ----------
        contextMenuActions : Optional[Callable[[QtGui.QView], List[MenuAction]]]
        parent : Optional[QtWidgets.QWidget]
        '''
        if not contextMenuActions:
            contextMenuActions = self.defaultContextMenuActions
        super(ContextMenuMixin, self).__init__(parent=parent)
        assert isinstance(self, QtWidgets.QWidget)
        contextMenuActions = contextMenuActions(self)
        self._contextMenuBuilder = MenuBuilder('_context_', contextMenuActions)

    # Qt methods ---------------------------------------------------------------
    def contextMenuEvent(self, event):
        context = self.GetMenuContext()
        menu = self._contextMenuBuilder.Build(context, parent=self)
        if menu:
            menu.exec_(event.globalPos())
            event.accept()

    # Custom methods -----------------------------------------------------------
# TODO: Get rid of this
    def GetSignal(self, name):
        # type: (str) -> QtCore.Signal
        '''Search through all actions on the menu-builder for a signal object.

        Parameters
        ----------
        name : str
            name of an attribute holding a signal

        Returns
        -------
        QtCore.Signal
        '''
        # search the view and then the menu and menu actions for a signal
        toSearch = [self]
        toSearch.extend(self._contextMenuBuilder.actions)
        for obj in toSearch:
            signal = getattr(obj, name, None)
            if signal and isinstance(signal, QtCore.Signal):
                return signal
        raise ValueError('Signal not found: {} in any of {}'.format(
            name, ', '.join([x.__class__.__name__ for x in toSearch])))
# TODO: Get rid of view
    def defaultContextMenuActions(self, view):
        # type: (QtGui.QView) -> List[MenuAction]
        '''Override with default context menu actions

        Parameters
        ----------
        view : QtGui.QView

        Returns
        -------
        List[MenuAction]
        '''
        raise ValueError('must provide context menu actions for this class')

    def GetMenuContext(self):
        # type: () -> Context
        '''Override this to return contextual information to your menu actions.

        Returns
        -------
        Context
        '''
        raise NotImplementedError


# class SelectionContextMenuMixin(ContextMenuMixin):
#     def GetSelectedRowItems(self):
#         # type: () -> List[T]
#         '''
#         Returns
#         -------
#         List[T]
#         '''
#         indexes = self.selectionModel().selectedRows()
#         return [index.internalPointer() for index in indexes]
#
#     def GetContext(self):
#         # type: () -> Context
#         # FIXME: create a Context here that includes self, selection, etc
#         return self.GetSelectedRowItems()



# FIXME: Don't pass role stuff to this
# TODO: Need aboutToShow context behavior
class MenuBarBuilder(object):
    '''Creates a menu bar that can be added to UIs'''
    def __init__(self, contextProvider, menuBuilders=None, parent=None):
        # type: (Any, Optional[QtWidgets.QWidget]) -> None
        '''
        Parameters
        ----------
        contextProvider : Any
            Object which implements a `GetMenuContext` method.
        menuBuilders : Optional[Iterable[MenuBuilder]]
            MenuBuilder instances to add to the menu bar.
        parent : Optional[QtWidgets.QWidget]
            Optional parent for the created `QMenuBar`.
        '''
        self.contextProvider = contextProvider
        self._menus = {}  # type: Dict[str, QtWidgets.QMenu]
        self._menuBuilders = {}  # type: Dict[str, MenuBuilder]
        self._menuBar = QtWidgets.QMenuBar(parent=parent)
        if menuBuilders:
            for builder in menuBuilders:
                self.AddMenu(builder)

    @property
    def menuBar(self):
        return self._menuBar

    def _menuAboutToShow(self, menuName):
        menu = self._menus[menuName]
        context = self.contextProvider.GetMenuContext()
        for action in menu.actions():
            actionBuilder = action.data()
            if actionBuilder and isinstance(actionBuilder, MenuAction):
                actionBuilder.Update(action, context)

    def AddMenu(self, menuBuilder):
        '''Register a new menu from a `MenuBuilder`.

        Parameters
        ----------
        menuBuilder : MenuBuilder

        Returns
        -------
        bool
            Whether a new menu was added to the menu bar.
        '''
        name = menuBuilder.name
        if name in self._menus:
            raise ValueError('A menu named %s already exists' % name)
        context = self.contextProvider.GetMenuContext()
        menu = menuBuilder.Build(context, parent=self._menuBar)
        if menu:
            self._menuBar.addMenu(menu)
            menu.aboutToShow.connect(partial(self._menuAboutToShow, name))
            self._menus[name] = menu
            self._menuBuilders[name] = menuBuilder
            return True
        return False

    def GetMenu(self, name):
        # type: (str) -> Optional[QtWidgets.QMenu]
        '''Get a registered menu by name.

        Parameters
        ----------
        name : str

        Returns
        -------
        Optional[QtWidgets.QMenu]
        '''
        return self._menus.get(name)

    def GetMenuBuilder(self, name):
        # type: (str) -> Optional[MenuBuilder]
        '''Get a registered menu builder by name.

        Parameters
        ----------
        name : str

        Returns
        -------
        Optional[MenuBuilder]
        '''
        return self._menuBuilders.get(name)


class UsdQtUtilities(object):
    '''
    Aggregator for customizable utilities in a usdQt app.

    To overwrite the default implementation, just define a function and then
    call:
    UsdQtUtilities.register('someName', func)
    '''
    _registered = {}

    @classmethod
    def register(cls, name, func):
        cls._registered.setdefault(name, []).insert(0, func)

    @classmethod
    def exec_(cls, name, *args, **kwargs):
        for func in cls._registered[name]:
            try:
                return func(*args, **kwargs)
            except FallbackException:
                continue


def GetReferencePath(parent, stage=None):
    '''
    Overrideable func for getting the path for a new reference from a user.

    Use UsdQtUtilities to provide your pipeline specific file browser ui.
    '''
    name, _ = QtWidgets.QInputDialog.getText(
        parent,
        'Add Reference',
        'Enter Usd Layer Identifier:')
    return name


def GetId(layer):
    '''
    Overrideable func to get the unique key used to store the original
    contents of a layer.

    Use UsdQtUtilities to provide support for pipeline specific resolvers that
    may need special handling.
    '''
    if isinstance(layer, Sdf.Layer):
        return layer.identifier
    else:
        return layer


UsdQtUtilities.register('GetReferencePath', GetReferencePath)
UsdQtUtilities.register('GetId', GetId)
