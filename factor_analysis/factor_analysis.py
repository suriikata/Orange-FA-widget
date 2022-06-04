import numpy as np

from sklearn.decomposition import FactorAnalysis

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

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        sample = Output("Sampled Data", Table)

    n_components = settings.ContextSetting(1)
    setting_for_rotation = settings.Setting(Rotation.NoRotation)
    autocommit = settings.Setting(True)
    
    def __init__(self):
        super().__init__()  # since OWFactorAnalysis is a derivative of OWWidget, first intialize OWFA
        self.dataset = None

        # Main area settings
        self.mainArea.setVisible(True)

        self.attr_box = gui.hBox(self.mainArea, margin=0)
        
        gui.spin(
            self.attr_box, self, "n_components", label="Number of components:",
            minv=1, maxv=100, step=1, controlWidth=30, 
            callback=[self.factor_analysis, self.commit.deferred],  # deferred = zapoznelo
        )
        
        gui.comboBox(
            self.attr_box, self, "setting_for_rotation", label="Rotation:", labelWidth=50,
            items=Rotation.items(), orientation=Qt.Horizontal, 
            contentsLength=12, callback=self.factor_analysis
        )

        gui.auto_commit(
            self.attr_box, self, 'autocommit', 'Commit',
            orientation=Qt.Horizontal
        )
        gui.separator(self.mainArea) # do i need it? >>> the first element in mainArea

        box = gui.vBox(self.mainArea, box = "Factor Loadings")
        
        self.tablemodel = QStandardItemModel(self)
        view = self.tableview = QTableView(
            editTriggers=QTableView.NoEditTriggers)
        view.setModel(self.tablemodel)
        view.horizontalHeader().hide()
        view.verticalHeader().hide()
        view.horizontalHeader().setMinimumSectionSize(60)
        #view.selectionModel().selectionChanged.connect(self._invalidate)
        view.setShowGrid(True)
        #view.setItemDelegate(BorderedItemDelegate(Qt.white))
        view.setSizePolicy(QSizePolicy.MinimumExpanding,
                           QSizePolicy.MinimumExpanding)
        # view.clicked.connect(self.cell_clicked)
        box.layout().addWidget(view)

        self.plot = SliderGraph("Factor 1", "Factor 2", self.prazna_funkcija)
        self.mainArea.layout().addWidget(self.plot)

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
        for j in range(len(self.dataset.domain.attributes)):
            name = self.dataset.domain.attributes[j].name
            self.insert_item(0, j + 1, name)        #in order to get the first cell in column > increase j for 1

        for i in range(self.n_components):
            name = f"Factor {i + 1}"
            self.insert_item(i + 1, 0, name)        #in order to get the first cell in row > increase i for 1

        for i in range(len(self.result.X)):         #i = rows = factors
            for j in range(len(self.result.X[0])):  #j = columns = variables
                val = self.result.X[i][j]           #from i-row and j-column we had a specific variable value
                self.insert_item(i + 1, j + 1, val)     #insert into rows and column from 1 onwards, because everything is full of names

    def prazna_funkcija(self): # bc _init_ Slidergrapha requires "callback"
        pass

    def get_range(self, factor):
        max_value = factor[0]
        for i in range(len(factor)):
            if factor[i] > max_value:
                max_value = factor[i]

        min_value = factor[0]
        for i in range(len(factor)):
            if factor[i] < min_value:
                min_value = factor[i]

        # adjust and scale by 0.1
        min_value = min_value - 0.1 * abs(min_value)
        max_value = max_value + 0.1 * abs(max_value)

        # return the abs value of maximum
        return max(abs(min_value), abs(max_value))

    def set_range(self):
        factor1_range = self.get_range(self.factor1)
        factor2_range = self.get_range(self.factor2)
        self.plot.setRange(xRange=(-factor1_range, factor1_range), yRange=(-factor2_range, factor2_range))


    def setup_plot(self):
        self.plot.clear_plot()
        if self.n_components == 1:
            return

        self.factor1 = self.result.X[0]
        self.factor2 = self.result.X[1]

        self.set_range()

        foreground = self.plot.palette().text().color()
        foreground.setAlpha(128)

        names = []
        for i in range(len(self.dataset.domain.attributes)):
            name = self.dataset.domain.attributes[i].name
            names.append(name)

        for x, y, n in zip(self.factor1, self.factor2, names):
            x_vektor, y_vektor = [0, x], [0, y]
            self.plot.plot(x_vektor, y_vektor, pen=mkPen(QColor(Qt.red) , width=1), antialias=True)

            if n is not None:
                label = TextItem(
                    text=n, anchor=(0, 1), color=foreground)
                label.setPos(x_vektor[-1], y_vektor[-1])
                self.plot.x = x_vektor
                self.plot._set_anchor(label, len(x_vektor) - 1, True)
                self.plot.addItem(label)
        
        """
        #TABELA TODO: factor loadings po rotaciji 
        box = gui.vBox(self.mainArea, box = "Factor Loadings")
        #self.left_side.setContentsMargins(0,0,0,0)
        table = self.table_view = QTableView(self.mainArea)
        #table.setModel(self.table_model) ??? factorsko vnest
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
        #self.closeContext()
        if dataset is None:
            self.sample = None
        else:
            #self.openContext(dataset.domain)  # what is the function of context?
            pass

        self.dataset = dataset
        self.commit.now()

    def factor_analysis(self):
        # with chosen n_components and depending on the user-selected rotation, calculate the FA on self.dataset
        if self.setting_for_rotation == 0:
            result = FactorAnalysis(self.n_components).fit(self.dataset.X)
        elif self.setting_for_rotation == 1:
            result = FactorAnalysis(self.n_components, rotation="varimax").fit(self.dataset.X)
        elif self.setting_for_rotation == 2:
            result = FactorAnalysis(self.n_components, rotation="quartimax").fit(self.dataset.X)
        else:
            print("Error:")
    
        # from result variable (instance of class) only extract the table we are interested in (components)
        calculated_components = result.components_

        # transform the table back to Orange.data.Table
        self.result = Table.from_numpy(Domain(self.dataset.domain.attributes), 
                                      calculated_components)

    @gui.deferred
    def commit(self):
        if self.dataset is None:
            self.Outputs.sample.send(None)
        else:
            self.factor_analysis()
            # send self.result in Outputs channel
            self.Outputs.sample.send(self.result)
            self.insert_table()
            self.setup_plot()



if __name__ == "__main__":
    WidgetPreview(OWFactorAnalysis).run(Table("iris"))