"""Parameter and effect-panel widgets."""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from digart.effects.base import Effect, ParamDef


class ParamWidget(QWidget):
    """Base class for a single parameter control."""

    value_changed = Signal(object)

    def __init__(self, param: ParamDef, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.param = param
        self._build_ui()
        self.set_value(param.default)

    def _build_ui(self) -> None:
        raise NotImplementedError

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError

    def _emit(self) -> None:
        self.value_changed.emit(self.get_value())


class IntParamWidget(ParamWidget):
    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(self.param.min))
        self.slider.setMaximum(int(self.param.max))
        self.slider.setSingleStep(int(self.param.step or 1))
        self.spin = QSpinBox()
        self.spin.setMinimum(int(self.param.min))
        self.spin.setMaximum(int(self.param.max))
        self.spin.setSingleStep(int(self.param.step or 1))

        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.spin.valueChanged.connect(self._emit)

        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin, 0)

    def get_value(self) -> int:
        return self.spin.value()

    def set_value(self, value: Any) -> None:
        self.spin.setValue(int(value))


class FloatParamWidget(ParamWidget):
    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(10000)
        self.spin = QDoubleSpinBox()
        self.spin.setMinimum(float(self.param.min))
        self.spin.setMaximum(float(self.param.max))
        self.spin.setSingleStep(float(self.param.step or 0.1))
        self.spin.setDecimals(3)

        self.slider.valueChanged.connect(self._slider_to_spin)
        self.spin.valueChanged.connect(self._spin_to_slider)
        self.spin.valueChanged.connect(self._emit)

        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin, 0)

    def _slider_to_spin(self, value: int) -> None:
        rng = float(self.param.max) - float(self.param.min)
        fraction = value / 10000.0
        self.spin.setValue(float(self.param.min) + fraction * rng)

    def _spin_to_slider(self, value: float) -> None:
        rng = float(self.param.max) - float(self.param.min)
        if rng == 0:
            fraction = 0
        else:
            fraction = (value - float(self.param.min)) / rng
        self.slider.blockSignals(True)
        self.slider.setValue(int(fraction * 10000))
        self.slider.blockSignals(False)

    def get_value(self) -> float:
        return self.spin.value()

    def set_value(self, value: Any) -> None:
        self.spin.setValue(float(value))


class BoolParamWidget(ParamWidget):
    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox(self.param.label)
        self.checkbox.stateChanged.connect(self._emit)
        layout.addWidget(self.checkbox)

    def get_value(self) -> bool:
        return self.checkbox.isChecked()

    def set_value(self, value: Any) -> None:
        self.checkbox.setChecked(bool(value))


class ChoiceParamWidget(ParamWidget):
    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.combo.addItems(list(self.param.choices))
        self.combo.currentTextChanged.connect(lambda _: self._emit())
        layout.addWidget(QLabel(self.param.label))
        layout.addWidget(self.combo, 1)

    def get_value(self) -> str:
        return self.combo.currentText()

    def set_value(self, value: Any) -> None:
        idx = self.combo.findText(str(value))
        if idx >= 0:
            self.combo.setCurrentIndex(idx)


def _build_param_widget(param: ParamDef) -> ParamWidget:
    if param.type == "int":
        return IntParamWidget(param)
    if param.type == "float":
        return FloatParamWidget(param)
    if param.type == "bool":
        return BoolParamWidget(param)
    if param.type == "choice":
        return ChoiceParamWidget(param)
    raise ValueError(f"Unknown param type: {param.type}")


class EffectPanel(QGroupBox):
    """Collapsible panel for one effect: enable checkbox + parameter widgets."""

    configuration_changed = Signal()

    def __init__(self, effect: Effect, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.effect = effect
        self._param_widgets: dict[str, ParamWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.setTitle(self.effect.name.upper())
        self.setCheckable(True)
        self.setChecked(False)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 20, 10, 10)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        for row, param in enumerate(self.effect.params):
            label = QLabel(param.label)
            widget = _build_param_widget(param)
            widget.value_changed.connect(self.configuration_changed)
            self._param_widgets[param.name] = widget
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)

        layout.addLayout(grid)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("panel-separator")
        layout.addWidget(line)

        self.toggled.connect(self.configuration_changed)

    def is_enabled(self) -> bool:
        return self.isChecked()

    def get_params(self) -> dict[str, Any]:
        return {name: widget.get_value() for name, widget in self._param_widgets.items()}

    def set_params(self, params: dict[str, Any]) -> None:
        for name, value in params.items():
            if name in self._param_widgets:
                self._param_widgets[name].set_value(value)

    def reset_params(self) -> None:
        for param in self.effect.params:
            self._param_widgets[param.name].set_value(param.default)
