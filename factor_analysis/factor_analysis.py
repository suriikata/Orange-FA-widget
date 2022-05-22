import numpy

from sklearn.decomposition import FactorAnalysis

from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QTableView

from Orange.data import Table, Domain
from Orange.widgets import settings
from Orange.widgets.widget import OWWidget
from orangewidget.widget import Input, Output
from orangewidget.utils.widgetpreview import WidgetPreview
from Orange.widgets.utils.slidergraph import SliderGraph
from orangewidget import gui


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
    
    def __init__(self): # __init__ je konstruktor (prva metoda ki se klice, ko se ustvari instance tega razreda)
        super().__init__()  # Ker je OWFactorAnalysis derivat OWWIdgeta (deduje iz OWWidgeta), najprej inicializiram njega
        self.dataset = None
       
        # Control area settings
        self.optionsBox = gui.widgetBox(self.controlArea, "Options")
        gui.spin(
            self.optionsBox, self, "n_components", label="Number of components:",
            minv=1, maxv=100, step=1,
            callback=[self.factor_analysis, self.commit.deferred], #deferred = zapoznelo
        )
        
        gui.comboBox(
            self.optionsBox, self, "setting_for_rotation", label = "Rotation:",
            items=Rotation.items(), orientation=Qt.Horizontal,
            labelWidth=90, callback=self.factor_analysis
        )

        gui.auto_commit(
            self.controlArea, self, 'autocommit', 'Commit',
            orientation=Qt.Horizontal
        )
        gui.separator(self.controlArea)  # TODO tega mogoce ne potrebujem ker je to za zadnjim elementom v controlArea

        # Main area settings
        self.mainArea.setVisible(True)

        gui.separator(self.mainArea) # TODO tega mogoce ne potrebujem, ker je to pred prvim elementom v mainArea

        self.plot = SliderGraph("Factor 1", "Factor 2", self.prazna_funkcija)

        self.mainArea.layout().addWidget(self.plot)

    def prazna_funkcija(self): #zato ker _init_ Slidergrapha zahteva "callback"
        pass

    def setup_plot(self):
        if self.n_components == 1:
            return

        self.factor1 = self.result.X[0]
        self.factor2 = [self.result.X[1]]

        self.plot.setRange(xRange=(-10.0, 10.0), yRange=(-10.0, 10.0))

        print(self.factor1)

        self.plot.update(x = self.factor1, y = self.factor2, colors = [Qt.red])

        """ TABELA TODO: factor loadings po rotaciji 
        box = gui.vBox(self.mainArea, box = "Eigenvalue Scores")
        self.left_side.setContentsMargins(0,0,0,0)
        table = self.table_view = QTableView(self.mainArea)
        #table.setModel(self.table_model)
        table.setSelectionMode(QTableView.SingleSelection)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setItemDelegate(gui.ColoredBarItemDelegate(self, color=Qt.cyan))
        #table.selectionModel().selectionChanged.connect(self.select_row)
        table.setMaximumWidth(300)
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
            #self.openContext(dataset.domain)  #Kaj je funkcija contexta
            pass

        self.dataset = dataset
        self.optionsBox.setDisabled(False)
        self.commit.now() # Takoj poklici metodo commit

    def factor_analysis(self):
        # Z izbranimi n_componentami in v odvisnosti od uporabnisko izbrane rotacije, izracunaj FA na self.dataset
        if self.setting_for_rotation == 0:
            result = FactorAnalysis(self.n_components).fit(self.dataset.X)
        elif self.setting_for_rotation == 1:
            result = FactorAnalysis(self.n_components, rotation="varimax").fit(self.dataset.X)
        elif self.setting_for_rotation == 2:
            result = FactorAnalysis(self.n_components, rotation="quartimax").fit(self.dataset.X)
        else:
            print("Error: To pa ne bi smelo zgoditi tako")
    
        # Iz spremenljivke result (ki je instanca nekega razreda) izlusci samo tabelo, ki nas zanima (komponente)
        calculated_components = result.components_

        # Pretvori tabelo nazaj v Orange.data.Table
        self.result = Table.from_numpy(Domain(self.dataset.domain.attributes),
                                       calculated_components)



    @gui.deferred
    def commit(self):
        if self.dataset is None:
            self.Outputs.sample.send(None)
        else:
            self.factor_analysis()
            # Poslji self.result v Outputs channel.
            self.Outputs.sample.send(self.result)
            self.setup_plot()


if __name__ == "__main__":
    WidgetPreview(OWFactorAnalysis).run(Table("iris"))