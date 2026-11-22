import {
  ElAlert,
  ElButton,
  ElConfigProvider,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElInput,
  ElInputNumber,
  ElOption,
  ElPopover,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElSlider,
  ElTag,
} from 'element-plus'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/dropdown/style/css'
import 'element-plus/es/components/empty/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/input-number/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/popover/style/css'
import 'element-plus/es/components/radio/style/css'
import 'element-plus/es/components/radio-button/style/css'
import 'element-plus/es/components/radio-group/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/slider/style/css'
import 'element-plus/es/components/tag/style/css'

const components = [
  ElAlert,
  ElButton,
  ElConfigProvider,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElInput,
  ElInputNumber,
  ElOption,
  ElPopover,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElSlider,
  ElTag,
]

export default {
  install(app) {
    for (const component of components) {
      app.component(component.name, component)
    }
  },
}
