import numpy as np

from sklearn.decomposition import FactorAnalysis
from factor_analyzer import FactorAnalyzer

from AnyQt.QtCore import Qt
from AnyQt.QtGui import QColor, QBrush, QStandardItemModel, QStandardItem
from AnyQt.QtWidgets import QTableView, QSizePolicy

from Orange.data import Table, Domain
from Orange.data.util import get_unique_names
from Orange.widgets import settings
from Orange.widgets.widget import OWWidget
from orangewidget.widget import Input, Output
from orangewidget.utils.widgetpreview import WidgetPreview
from Orange.widgets.utils.slidergraph import SliderGraph
from orangewidget import gui

from pyqtgraph import mkPen, TextItem

"""
TVORNICA IZBOLJŠAV:
    i. aplicirati rotation funkcijo >>>> vrednosti se ne spremenijo; 
    ii. correlation matrix z radiobutonni (OW Continuize) + prikazati na grafu;
    iii. najti oblimin funkcijo(!);
    iv. obarvati in poudariti pomembne variable;
    v. definirati errorje;
    vi. izhajati iz plotutils namesto slidergrapha razreda;
    vii. input data: fa na sparse matrix.
"""
BorderRole = next(gui.OrangeUserRole)

class Rotation:
    NoRotation, Varimax, Quartimax = 0, 1, 2

    @staticmethod
    def items():
        return ["NoRotation", "Varimax", "Quartimax"]

class OWFactorAnalysis(OWWidget):
    name = "Factor Analysis"
    description = "Randomly selects a subset of instances from the dataset."
    icon = "icons/DataSamplerB.svg"
    priority = 20

    want_control_area = False

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        sample = Output("Sampled Data", Table)

    n_components = settings.ContextSetting(1)
    rotation = settings.Setting(Rotation.NoRotation)
    autocommit = settings.Setting(True)
    
    def __init__(self):
        self.dataset = None
        self.attributes = None
        self.fa_loadings = None
        self.header = []

        # Main area settings
        self.attr_box = gui.hBox(self.mainArea, margin=0)
        
        gui.spin(
            self.attr_box, self, "n_components", label="Number of components:",
            minv=1, maxv=100, step=1, controlWidth=30, 
            callback=self.n_components_changed,
        )

        gui.comboBox(
            self.attr_box, self, "rotation", label="Rotation:", labelWidth=50,
            items=Rotation.items(), orientation=Qt.Horizontal, 
            contentsLength=12, callback=self.factor_analysis
        )

        gui.auto_commit(
            self.attr_box, self, 'autocommit', 'Commit',
            orientation=Qt.Horizontal
        )

        gui.separator(self.mainArea)

        box = gui.vBox(self.mainArea, box = "Factor Loadings")
        
        self.tablemodel = QStandardItemModel(self)
        self.tablemodel.setHorizontalHeaderLabels(self.header)
        view = self.tableview = QTableView(
            editTriggers=QTableView.NoEditTriggers)
        view.setModel(self.tablemodel)
        view.horizontalHeader()
        view.verticalHeader()
        view.horizontalHeader().setMinimumSectionSize(60)
        #view.selectionModel().selectionChanged.connect(self._invalidate)
        view.setShowGrid(True)
        #view.setItemDelegate(BorderedItemDelegate(Qt.white))
        view.setSizePolicy(QSizePolicy.MinimumExpanding,
                           QSizePolicy.MinimumExpanding)
        # view.clicked.connect(self.cell_clicked)
        box.layout().addWidget(view)

        self.plot = SliderGraph("Factor 1", "Factor 2", lambda x: None)
        self.mainArea.layout().addWidget(self.plot)

    def n_components_changed(self):
        self.factor_analysis()
        self.commit.deferred()

    def insert_item(self, i, j, val):
        """
        insert item into row i and column j
        """
        # col_val = colors[i, j]        #colored it by the relevance, at some point
        item = QStandardItem()          # what is QStandardItem??
        bkcolor = QColor.fromHsl([0, 240][i == j], 160, 255)
        item.setData(QBrush(bkcolor), Qt.BackgroundRole)
        # bkcolor is light-ish so use a black text
        item.setData(QBrush(Qt.black), Qt.ForegroundRole)
        item.setData("trbl", BorderRole)
        # item.setToolTip("actual: {}\npredicted: {}".format(
        # self.headers[i], self.headers[j]))
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        if type(val) != str:
            val = str(round(val, 2))

        item.setData(val, Qt.DisplayRole)          # set our val into item
        self.tablemodel.setItem(i, j, item)

    def insert_table(self):
        #insert variable names into first row (0)
        for j in range(len(self.attributes)):
            self.header.append(self.attributes[j].name)

        self.tablemodel.setHorizontalHeaderLabels(self.header)
        self.header = []

        for i in range(len(self.fa_loadings.X)):         #i = rows = factors
            for j in range(len(self.fa_loadings.X[0])):  #j = columns = variables
                val = self.fa_loadings.X[i][j]           #from i-row and j-column we had a specific variable value
                self.insert_item(i, j, val)      #insert into rows and column from 1 onwards, because everything is full of names


    def set_range(self):
        factor1_range = np.max(1.1 * np.abs(self.factor1))  #function to remember > the largest abs value * 1.1 of factor
        factor2_range = np.max(1.1 * np.abs(self.factor2))
        self.plot.setRange(xRange=(-factor1_range, factor1_range), yRange=(-factor2_range, factor2_range))


    def setup_plot(self):
        self.plot.clear_plot()
        if self.n_components == 1:
            return

        self.factor1 = self.fa_loadings.X[0]
        self.factor2 = self.fa_loadings.X[1]

        self.set_range()

        foreground = self.plot.palette().text().color()
        foreground.setAlpha(128)

        for x, y, attr in zip(self.factor1, self.factor2, self.attributes):
            x_vector, y_vector = [0, x], [0, y]
            self.plot.plot(x_vector, y_vector,
                pen=mkPen(QColor(Qt.red), width=1), antialias=True,
            )

            label = TextItem(text=attr.name, anchor=(0, 1), color=foreground)
            label.setPos(x_vector[-1], y_vector[-1])
            self.plot.x = x_vector
            self.plot._set_anchor(label, len(x_vector) - 1, True)
            self.plot.addItem(label)
        
        """
        #TABELA TODO: factor loadings po rotaciji 
        box = gui.vBox(self.mainArea, box = "Factor Loadings")
        #self.left_side.setContentsMargins(0,0,0,0)
        table = self.table_view = QTableView(self.mainArea)
        #table.setModel(self.table_model) ??? faktorsko vnest
        #table.setSelectionMode(QTableView.SingleSelection)
        #table.setSelectionBehavior(QTableView.SelectRows)
        #table.setItemDelegate(gui.ColoredBarItemDelegate(self, color=Qt.cyan))
        #table.selectionModel().selectionChanged.connect(self.select_row)
        #table.setMaximumWidth(300)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().hide()
        table.setShowGrid(False)
        box.layout().addWidget(table)
        """

    @Inputs.data
    def set_data(self, dataset):
        self.dataset = dataset
        self.attributes = self.dataset.domain.attributes
        self.commit.now()


    def factor_analysis(self):              #GROMOZANSKI, V OČI BODEČ HROŠČ
        # with chosen n_components and depending on the user-selected rotation, calculate the FA on self.dataset
        if self.rotation == Rotation.NoRotation:
            fa = FactorAnalysis(self.n_components)
        elif self.rotation == Rotation.Varimax:
            fa = FactorAnalysis(self.n_components, rotation="varimax")
        else:
            fa = FactorAnalysis(self.n_components, rotation="quartimax")
        fa_rotation_result = fa.fit(self.dataset.X)
    
        # from result variable (instance of class) only extract the table we are interested in (components)
        calculated_components = fa_rotation_result.components_

        # transform the table back to Orange.data.Table
        self.fa_loadings = Table.from_numpy(Domain(self.attributes),
                                      calculated_components)

    def factor_analysis2(self):
        fa = FactorAnalyzer(rotation = None, n_factors = self.n_components)
        fa.fit(self.dataset.X)
        eigen = fa.get_eigenvalues()
        print(eigen)

    @gui.deferred
    def commit(self):
        if self.dataset is None:
            self.Outputs.sample.send(None)
        else:
            self.factor_analysis()
            self.factor_analysis2()
            # send self.fa_loadings in Outputs channel
            self.Outputs.sample.send(self.fa_loadings)
            self.insert_table()
            self.setup_plot()



if __name__ == "__main__":
    WidgetPreview(OWFactorAnalysis).run(Table("iris"))