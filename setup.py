from setuptools import setup

setup(name="Demo Faktorska Analiza",
      packages=["factor_analysis"],
      package_data={"factor_analysis": ["icons/*.svg"]},
      classifiers=["Example :: Invalid"],
      # Declare factor_analysis package to contain widgets for the "factor_analysis" category
      entry_points={"orange.widgets": "Demo = factor_analysis"},
      )