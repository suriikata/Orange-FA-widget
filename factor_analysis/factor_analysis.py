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

# user selects type of rotation
class Rotation:
    NoRotation, Varimax, Promax, Oblimin, Oblimax, Quartimin, Quartimax, Equamax = 0, 1, 2, 3, 4, 5, 6, 7

    @staticmethod
    def items():
        return ["NoRotation", "Varimax", "Promax", "Oblimin", "Oblimax", "Quartimin", "Quartimax", "Equamax"]

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
        self.dataset = None     # this contains the input dataset.
        self.attributes = []    # this contains the list of attribute (variable) names.
        self.fa_loadings = None # this contains factorial values after rotation was applied.

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

        # Table
        self.tablemodel = QStandardItemModel(self)
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

        # Graph
        self.plot = SliderGraph("Factor 1", "Factor 2", lambda x: None)
        self.mainArea.layout().addWidget(self.plot)

    def n_components_changed(self):
        self.factor_analysis()
        self.commit.deferred()

    @Inputs.data
    def set_data(self, dataset):
        self.dataset = dataset

        # Extract list of attribute (variables) names from the self.dataset.domain.attributes
        self.attributes = []
        for j in range(len(self.dataset.domain.attributes)):
            self.attributes.append(self.dataset.domain.attributes[j].name)
        self.commit.now()

    # insert item into row i and column j of the table.
    def insert_item(self, i, j, val):
        # col_val = colors[i, j]                # at some point, color it by the relevance
        item = QStandardItem()
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

    #set up the table which will be shown in the Main Area.
    def insert_table(self):
        #insert attribute (variable) names into horizontal header
        self.tablemodel.setHorizontalHeaderLabels(self.attributes)

        # TODO insert radiobox buttons

        #TODO insert eigen values

        #insert values into the table
        for i in range(len(self.fa_loadings.X)):         #i = rows = factors
            for j in range(len(self.fa_loadings.X[0])):  #j = columns = variables
                val = self.fa_loadings.X[i][j]           #from i-row and j-column we had a specific variable value
                self.insert_item(i, j, val)      #insert into rows and column from 1 onwards, because everything is full of names


    def setup_plot(self):
        self.plot.clear_plot()
        if self.n_components == 1:
            return

        #get first 2 factors to show on the graph
        self.factor1 = self.fa_loadings.X[0]
        self.factor2 = self.fa_loadings.X[1]

        #gset the range
        self.set_range_graph()

        foreground = self.plot.palette().text().color()
        foreground.setAlpha(128)

        #draw the variable vectors and their names into the graph
        for x, y, attr_name in zip(self.factor1, self.factor2, self.attributes):
            x_vector, y_vector = [0, x], [0, y]
            self.plot.plot(x_vector, y_vector,
                pen=mkPen(QColor(Qt.red), width=1), antialias=True,
            )

            label = TextItem(text=attr_name, anchor=(0, 1), color=foreground)
            label.setPos(x_vector[-1], y_vector[-1])
            self.plot.x = x_vector
            self.plot._set_anchor(label, len(x_vector) - 1, True)
            self.plot.addItem(label)
            # set range (scale) of the shown graph

    def set_range_graph(self):
        factor1_range = np.max(1.1 * np.abs(self.factor1))  # function to remember > the largest abs value * 1.1 of factor
        factor2_range = np.max(1.1 * np.abs(self.factor2))
        self.plot.setRange(xRange=(-factor1_range, factor1_range), yRange=(-factor2_range, factor2_range))


    def factor_analysis(self):              #GROMOZANSKI, V OČI BODEČ HROŠČ
        # with chosen n_components and depending on the user-selected rotation, calculate the FA on self.dataset
        rotation = [None, "Varimax", "Promax", "Oblimin", "Oblimax", "Quartimin", "Quartimax", "Equamax"][self.rotation]
        fit_result = FactorAnalyzer(rotation=rotation, n_factors=self.n_components).fit(self.dataset.X)

        # from result variable (instance of FactorAnalyzer class) only extract the loadings
        loadings = fit_result.loadings_

        # transform loadings in listicic
        loadings_list = []
        for x in loadings:
            loadings_list.append(x[0])

        loadings_list = np.asarray(loadings_list) # transform into nupmy array (maybe not necessry)
        print(f"len: {len(loadings_list)}, list of loadings: {loadings_list}")

        # from result variable (instance of FactorAnalyzer class) get the eigenvalues
        eigen_values = fit_result.get_eigenvalues()

    
       # transform the table back to Orange.data.Table
        print(f": X shape 1: {self.dataset.X[1]} <--> {len(self.dataset.domain.attributes)} domain attributes")

        self.fa_loadings = Table.from_numpy(Domain(self.dataset.domain.attributes), loadings_list)

    @gui.deferred
    def commit(self):
        if self.dataset is None:
            self.Outputs.sample.send(None)
        else:
            self.factor_analysis()
            # send self.fa_loadings in Outputs channel
            self.Outputs.sample.send(self.fa_loadings)
            self.insert_table()
            self.setup_plot()



if __name__ == "__main__":
    WidgetPreview(OWFactorAnalysis).run(Table("iris"))