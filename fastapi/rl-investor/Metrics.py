import numpy as np
from matplotlib import pyplot as plt

def compute_metrics(portfolio_values, risk_free_rate=.03, min_acceptable_retrun=0.03):
    portfolio_values = np.array(portfolio_values)

    daily_returns = np.diff(portfolio_values) / portfolio_values[:-1]

    #Convert annual rates to daily
    daily_rf = risk_free_rate / 252
    daily_mar = min_acceptable_retrun / 252

    cumulative_return = (portfolio_values[-1] / portfolio_values[0]) - 1.0

    excess_returns = daily_returns - daily_rf
    sharpe_ratio = np.mean(excess_returns) / max(np.std(excess_returns), 1e-4) * np.sqrt(252)

    downside_returns = np.minimum(daily_returns - daily_mar, 0)
    downside_std = np.sqrt(np.mean(downside_returns ** 2) + 1e-8)
    sortino = ((np.mean(daily_returns) - daily_mar) / downside_std) * np.sqrt(252)

    gains = np.sum(np.maximum(daily_returns - daily_mar, 0))
    losses = np.sum(np.maximum(daily_mar - daily_returns, 0))
    omega_ratio = gains / (losses + 1e-8)

    return {
        "cumulative_return": cumulative_return,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino,
        "omega_ratio": omega_ratio
    }

def plot_portfolio_performance(all_results, dataset_labels, save_path=None):
    num_datasets = len(all_results)
    fig, axes = plt.subplots(num_datasets, 1, facecolor='#0d1117')

    if num_datasets == 1:
        axes = [axes]

    for ax, results, label in zip(axes, all_results, dataset_labels):
        portfolio_values = [r['portfolio_value'] for r in results]
        steps = list(range(len(portfolio_values)))

        #Normalize to starting value
        start_value = portfolio_values[0] if portfolio_values[0] != 0 else 1.0
        normalized = np.array(portfolio_values) / start_value
        ax.set_facecolor('#0d1117')
        ax.plot(steps, normalized, label=label, color='#58a6ff', linewidth=1.5)

        #Reference line at 1 (no gain no loss)
        ax.axhline(y=1.0, color='#8b949e', linestyle='--', linewidth=.8, alpha=.6)

        ax.set_title(f"Dataset {label}", color='#e6edf3', fontsize=13, pad=10)
        ax.set_xlabel("Trading Days", color='#8b949e', fontsize=11)
        ax.yaxis.get_major_formatter().set_useOffset(False)
        ax.set_ylabel('Return (%)', color='#8b949e')
        ax.tick_params(colors='#8b949e')

        ax.spines['bottom'].set_color('#30363d')
        ax.spines['left'].set_color('#30363d')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        ax.legend(facecolor='#161b22', labelcolor='#e6edf3', fontsize=10)
        ax.grid(alpha=.15, color='#8b949e')

    plt.suptitle("Portfolio Performance Over Time", color='#e6edf3', fontsize=16, y=1.01)
    fig.set_figheight(16)
    fig.set_figwidth(12)

    if save_path:
        plt.savefig(save_path, facecolor=fig.get_facecolor(), dpi=150, bbox_inches='tight')

    plt.show()



def plot_metrics_table(all_metrics, dataset_labels, save_path=None):
    metric_names = ['cumulative_return', 'sharpe_ratio', 'sortino_ratio', 'omega_ratio']
    display_names = ['Cumulative Return', 'Sharpe Ratio', 'Sortino Ratio', 'Omega Ratio']

    data = np.array([[metrics[name] for name in metric_names] for metrics in all_metrics])

    fig, ax = plt.subplots(figsize=(10, 2 + len(all_metrics) * 0.8), facecolor='#0d1117')
    ax.set_facecolor('#0d1117')

    table = ax.table(
        cellText=[[f"{v:.4f}" for v in row] for row in data],
        rowLabels=[f"Dataset {label}" for label in dataset_labels],
        colLabels=display_names,
        cellLoc='center',
        loc='center'
    )

    #Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.8)

    for (row, col), cell in table.get_celld().items():
        cell.set_facecolor('#161b22')
        cell.set_text_props(color='#e6edf3')
        cell.set_edgecolor('#30363d')

        #Highlight the header
        if row == 0 or col == -1:
            cell.set_facecolor('#1f6feb')
            cell.set_text_props(weight='bold', color='white')

        #Color positive values green, negative red
        if row > 0 and col >= 0:
            value = data[row-1, col]
            if value > 0:
                cell.set_facecolor('#0d2b0d')
            elif value < 0:
                cell.set_facecolor('#2b0d0d')

    ax.axis('off')
    ax.set_title("Performance Metrics Summary", color='#e6edf3', fontsize=14, pad=20)

    if save_path:
        plt.savefig(save_path, facecolor='#0d1117', dpi=150, bbox_inches='tight')

    plt.show()

