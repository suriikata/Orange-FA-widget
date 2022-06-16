import numpy as np

from sklearn.decomposition import FactorAnalysis
from factor_analyzer import FactorAnalyzer

from AnyQt.QtCore import Qt, QRectF
from AnyQt.QtGui import QColor, QBrush, QStandardItemModel, QStandardItem
from AnyQt.QtWidgets import QTableView, QSizePolicy, QGridLayout,QHeaderView

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
    i. aplicirati rotation funkcijo >>>> vrednosti se spremenijo le s COMMITOM; 
    ii. correlation matrix z radiobutonni (OW Kmeans) + prikazati na grafu;
    iii. ko zmanjšamo število faktorjev, le-ti v tabeli NE izginejo;
    iv. obarvati in poudariti pomembne variable;
    v. definirati errorje > ne moreš izbrat več faktorjev kot je spremenljivk;
    vi. izhajati iz plotutils namesto slidergrapha razreda;
    vii. input data: fa na sparse matrix.
"""
BorderRole = next(gui.OrangeUserRole)

# user selects type of rotation.
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
        self.eigen_values = None
        self.components_accumulation = [1]
        
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


        # Table
        box = gui.vBox(self.mainArea, box = "Factor Loadings")
        self.tablemodel = QStandardItemModel(self)
        view = self.tableview = QTableView(
            editTriggers=QTableView.NoEditTriggers)
        view.setModel(self.tablemodel)
        view.horizontalHeader()
        view.horizontalHeader().setMinimumSectionSize(40)
        view.verticalHeader()
        self.select2Header = Select2Header()
        view.setVerticalHeader(self.select2Header)
        #view.selectionModel().selectionChanged.connect(self._invalidate)
        view.setShowGrid(True)
        #view.setItemDelegate(BorderedItemDelegate(Qt.white))
        view.setSizePolicy(QSizePolicy.MinimumExpanding,
                           QSizePolicy.MinimumExpanding)
        # view.clicked.connect(self.cell_clicked)
        box.layout().addWidget(view)


        # Graph
        self.plot = SliderGraph("", "", lambda x: None)
        self.mainArea.layout().addWidget(self.plot)


    def n_components_changed(self):
        self.components_accumulation.append(self.n_components)

        self.factor_analysis()
        self.commit.deferred()

    # cleaning values in table after n_components was changed to a smaller value
    def clear_table(self):
        if len(self.components_accumulation) < 2:
            return

        prev_n_components = self.components_accumulation[-2]
        for i in range(prev_n_components):
            for j in range(1 + len(self.fa_loadings.X[0])):     #1 column for eigen + number of variables.
                self.insert_item(i, j, "")

    @Inputs.data
    def set_data(self, dataset):
        self.dataset = dataset

        # extract list of attribute (variables) names from the self.dataset.domain.attributes.
        self.attributes = []
        for j in range(len(self.dataset.domain.attributes)):
            self.attributes.append(self.dataset.domain.attributes[j].name)
        self.commit.now()

    # insert item into row i and column j of the table
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


    # set up the table which will be shown in the Main Area.
    def insert_table(self):
        # insert attribute (variable) names into horizontal header.
        hheader_labels = ["eigenvalues",]
        for att in self.attributes:
            hheader_labels.append(att)
        self.tablemodel.setHorizontalHeaderLabels(hheader_labels)

        # insert factor names into vertical header.
        vheader_labels = []
        for i in range(self.n_components):
            vheader_labels.append(f"F{i + 1}")
        self.tablemodel.setVerticalHeaderLabels(vheader_labels)

        self.clear_table()

        # insert eigen values.
        for factor in range(len(self.fa_loadings.X)):
            eigen = self.eigen_values[factor]
            self.insert_item(factor, 0, eigen)


        # insert values into the table.
        for i in range(len(self.fa_loadings.X)):         #i = rows = factors
            for j in range(len(self.fa_loadings.X[0])):  #j = columns = variables
                val = self.fa_loadings.X[i][j]           #from i-row and j-column we had a specific variable value
                self.insert_item(i, j + 1, val)          #insert into columns from 1 onwards, because of the first eigen row


    def setup_plot(self):
        print("klice se setup_plot")
        self.plot.clear_plot()
        if self.n_components == 1:
            return

        selected_factors = self.select2Header.selected
        print(f"izbrana: {selected_factors}")

        self.factor1 = self.fa_loadings.X[selected_factors[0]]
        self.factor2 = self.fa_loadings.X[selected_factors[1]]

        # assign names to axis based on factors selected.
        axis = self.plot.getAxis("bottom")
        axis.setLabel(f"Factor {selected_factors[0]}")
        axis = self.plot.getAxis("left")
        axis.setLabel(f"Factor {selected_factors[1]}")

        # set the range
        self.set_range_graph()

        foreground = self.plot.palette().text().color()
        foreground.setAlpha(128)

        # draw the variable vectors and their names into the graph.
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
        # with chosen n_components and depending on the user-selected rotation, calculate the FA on self.dataset.
        rotation = [None, "Varimax", "Promax", "Oblimin", "Oblimax", "Quartimin", "Quartimax", "Equamax"][self.rotation]
        fit_result = FactorAnalyzer(rotation=rotation, n_factors=self.n_components).fit(self.dataset.X)

        # transform loadings correct format.
        loadings = []
        for i in range(self.n_components):
            row = []
            for x in fit_result.loadings_:
                row.append(x[i])
            loadings.append(row)

        # from result variable (instance of FactorAnalyzer class) get the eigenvalues.
        self.eigen_values = fit_result.get_eigenvalues()
        self.eigen_values = self.eigen_values[0]             #take only the first of 2 arrays > TODO why 2
    
       # transform the table back to Orange.data.Table.
        self.fa_loadings = Table.from_numpy(Domain(self.dataset.domain.attributes), loadings)

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

class Select2Header(QHeaderView):
    def __init__(self):
        super().__init__(Qt.Vertical)
        self.selected = [0, 1]

        self.setSectionsClickable(True)
        self.setSelectionMode(QHeaderView.NoSelection)
        self.sectionClicked.connect(self._on_clicked)

    def _on_clicked(self, i):
        if i not in self.selected:
            removed = self.selected.pop(0)
            self.headerDataChanged(Qt.Vertical, removed, removed)
            self.selected = [self.selected[0], i]
        self.repaint()

    def sizeHint(self):
        size = super().sizeHint()
        size.setWidth(size.width() + size.height())
        return size

    def paintSection(self, painter, rect, section):
        painter.save()
        super().paintSection(painter, rect, section)
        painter.restore()
        painter.save()
        x, y = rect.x(), rect.y()
        w, h = rect.width(), rect.height()
        a = h * 0.4
        x += w - 1.5 * a
        y += (h - a) // 2
        painter.drawRoundedRect(QRectF(x, y, a, a), 2, 2)
        if section in self.selected:
            painter.setBrush(QBrush(painter.pen().color()))
            painter.drawRect(QRectF(x + a / 4, y + a / 4, a / 2, a / 2))
        painter.restore()

if __name__ == "__main__":
    WidgetPreview(OWFactorAnalysis).run(Table("iris"))