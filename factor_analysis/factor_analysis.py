import numpy

from sklearn.decomposition import FactorAnalysis

from Orange.data import Table
from Orange.widgets import settings
from Orange.widgets.widget import OWWidget
from orangewidget.widget import Input, Output
from orangewidget.utils.widgetpreview import WidgetPreview
from orangewidget import gui

class OWFactorAnalysis(OWWidget):
    name = "Factor Analysis"
    description = "Randomly selects a subset of instances from the dataset."
    icon = "icons/DataSamplerB.svg"
    priority = 20

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        sample = Output("Sampled Data", Table)

    want_main_area = False

    commitOnChange = settings.Setting(0)
    n_components = settings.Setting(1)

    def __init__(self):
        super().__init__()

        self.optionsBox = gui.widgetBox(self.controlArea, "Options")
        gui.spin(
            self.optionsBox,
            self,
            "n_components",
            minv=1,
            maxv=100,
            step=1,
            label="Number of components:",
            callback=[self.factor_analysis, self.checkCommit],
        )
        gui.checkBox(
            self.optionsBox, self, "commitOnChange", "Commit data on selection change"
        )
        gui.button(self.optionsBox, self, "Commit", callback=self.commit)
        self.optionsBox.setDisabled(True)

        gui.separator(self.controlArea)


    @Inputs.data
    def set_data(self, dataset):
        if dataset is not None:
            self.dataset = dataset
            self.optionsBox.setDisabled(False)
            self.factor_analysis()
        else:
            self.dataset = None
            self.sample = None
            self.optionsBox.setDisabled(False)
        self.commit()

    def factor_analysis(self):
        if self.dataset is None:
            return

        # Z izbranimi n_componentami izracunaj FA na self.dataset
        result = FactorAnalysis(self.n_components).fit(self.dataset.X)
        # Iz spremenljivke result (ki je nek razred) izlusci samo tabelo ki nas zanima
        self.components = result.components_

        # Pretvori tabelo nazaj v Orange.data.Table
        self.result = Table.from_numpy(self.dataset.domain, self.components)


    def commit(self):
        # Poslji self.result v Outputs channel.
        self.Outputs.sample.send(self.result)

    def checkCommit(self):
        if self.commitOnChange:
            self.commit()

if __name__ == "__main__":
    WidgetPreview(OWFactorAnalysis).run(Table("iris"))