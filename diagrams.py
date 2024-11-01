import pandas as pd
import numpy as np
import seaborn as sb
import matplotlib.pyplot as plt

def plot_all_time_perfomance (data: pd.DataFrame):
    # Set the style of the visualization
    sb.set_theme(style="whitegrid")

    # Create a plot with Seaborn (for example, a bar plot)
    plt.figure(figsize=(10, 6))
    ax = sb.barplot(x="finish_time", y="profit_loss", data=data)
    
    # Save the figure in SVG format
    ax.get_figure().savefig("seaborn_plot.svg", format='svg')

    # Save the figure in PNG format
    ax.get_figure().savefig("seaborn_plot.png", format='png')

    # Show the plot
    plt.show()