/**
 * Mock 数据层
 * ------------------------------------------------------------------
 * 浏览器（没有 window.chrome.webview / window.cef.message）直接打开 dist 时，
 * bridge.js 进入 mock 模式，由本文件模拟 7 个插件 + __core 的返回。
 * 所有数据均为虚构演示数据，不含真实账号/凭据。
 */

const HOUR = 3600
const DAY = 86400
const nowSec = () => Math.floor(Date.now() / 1000)

export const MOCK_DEVICE = {
  AppTitle: 'E听说',
  ClientType: 'PC',
  CopyRight: 'E听说原生复刻（学习用途）',
  Name: 'E听说',
  computername: 'ETS-DEMO-PC',
  OsBit: '64',
  SystemVersion: 'Windows 11 23H2',
  ProcessName: 'EtsReplica.exe',
  DwNum: '1',
  HDD: '512GB',
  IP2: '192.168.1.20',
  Version: '5.7.9',
  MAC: '00-11-22-33-44-55',
  SystemVersionNumber: '10.0.22631'
}

export const MOCK_ECARDS = [
  {
    id: '100000001', name: '上海九年级', grade: '九年级', grade_id: 5260, resource_id: '239',
    school_name: '上海市演示中学', class_name: '18', teacher_first_name: '王',
    expire_time: '2027-01-31 23:59:59', out_of_date: 0, actived: 1, rate_scale: 1,
    engine_area: 'shanghai', parent_resource_id: '274', cover: '', school_level: 1,
    class_number: 'C00000001', student_name: '演示同学', number: 'SHM00000001'
  },
  {
    id: '100000002', name: '上海八年级', grade: '八年级', grade_id: 5259, resource_id: '240',
    school_name: '上海市演示中学', class_name: '18', teacher_first_name: '王',
    expire_time: '2026-12-31 23:59:59', out_of_date: 0, actived: 1, rate_scale: 1,
    engine_area: 'shanghai', parent_resource_id: '274', cover: '', school_level: 1,
    class_number: 'C00000001', student_name: '演示同学', number: 'SHM00000002'
  },
  {
    id: '100000003', name: '上海七年级', grade: '七年级', grade_id: 5258, resource_id: '241',
    school_name: '上海市演示中学', class_name: '18', teacher_first_name: '王',
    expire_time: '2026-12-15 23:59:59', out_of_date: 0, actived: 1, rate_scale: 1,
    engine_area: 'shanghai', parent_resource_id: '274', cover: '', school_level: 1,
    class_number: 'C00000001', student_name: '演示同学', number: 'SHM00000003'
  }
]

export const MOCK_PROFILE = {
  recent_account_id: '100000001',
  user_type: 0,
  school_year_id: 263833,
  school_year_name: '初中',
  grade_id: 5260,
  grade_name: '九年级',
  class_grade: '九年级',
  province_id: 5269,
  province_name: '上海市',
  city_id: 5270,
  city_name: '上海市',
  name: '演示同学',
  phone: '138****0000',
  raw_phone: '13800000000',
  bind_mobile: '',
  cover: '',
  partner: 'common',
  push_switch: 1,
  can_change_phone: 1,
  can_change_name: 0,
  register_at: '2026-09-01 08:00:00',
  expire: nowSec() + 14 * DAY
}

// ---------------------------------------------------------------------------
// 作业 / 题目结构
// ---------------------------------------------------------------------------
const CONTENT_DEFS = [
  { stid: '900101', group: '朗读句子', first: '朗读句子', kind: 'read' },
  { stid: '900102', group: '朗读句子', first: '朗读句子', kind: 'read' },
  { stid: '900103', group: '朗读句子', first: '朗读句子', kind: 'read' },
  { stid: '900104', group: '交际应答', first: '快速应答', kind: 'dialogue' },
  { stid: '900105', group: '复述', first: '复述', kind: 'picture' },
  { stid: '900106', group: '表达', first: '话题表述', kind: 'picture' }
]

function makeContents() {
  return CONTENT_DEFS.map((d, i) => ({
    read_type: 5,
    is_repeat_type: d.kind === 'picture' ? 1 : 0,
    entity_foreign_id: '',
    ppr: 'mock-ppr.zip',
    entity_type: '1',
    size: 90000 + i * 13107,
    min_unit: 1,
    real_id: d.stid,
    group_name: d.group,
    code_id: 'st' + (i + 1),
    url: 'mock-content-' + d.stid + '.zip',
    first_type_name: d.first,
    mock_kind: d.kind
  }))
}

function makeStruct(setId, setName, contents) {
  return {
    template: { size: 1030317, id: '686', url: 'template_686.zip' },
    follow_type: 0,
    set_name: setName,
    contents,
    group_name: contents[0] ? contents[0].group_name : '',
    set_id: setId,
    zip_url: ''
  }
}

const DEMO_CONTENTS = makeContents()
const DEMO_STRUCT = makeStruct('958806', '上海市九年级上 Unit 2 英语听说模拟卷 01', DEMO_CONTENTS)

export const MOCK_HOMEWORK = [
  {
    id: '111203417', set_id: '958806', name: '(新题型) 9年级(上) U2A 听说模拟',
    set_name: '上海市九年级上 Unit 2 英语听说模拟卷 01', first_column_id: '1',
    first_column_name: '听说模拟', column: '单元测试', set_module_id: '4', set_module_name: '考试',
    status: 0, complete: 0, pass: 1, point: 0, total_point: 10, avg_point: 0,
    begin: nowSec() - 2 * DAY, end: nowSec() + 5 * DAY, overtime: 0, allow_overtime: 1,
    use_time: 0, difficulty_rate: 0.76, set_type: 1, exam: 0, lock: 0, engine_area: 'shanghai',
    need_redo: false, practice_count: 1, structs: [DEMO_STRUCT], contents: DEMO_CONTENTS
  },
  {
    id: '111203418', set_id: '958807', name: 'Unit 3 Jobs 同步练习',
    set_name: 'Unit 3 Jobs 听说同步', first_column_id: '2', first_column_name: '同步练习',
    column: '同步训练', set_module_id: '5', set_module_name: '听说同步',
    status: 0, complete: 0, pass: 0, point: 0, total_point: 10, avg_point: 0,
    begin: nowSec() - 1 * DAY, end: nowSec() + 2 * DAY, overtime: 0, allow_overtime: 1,
    use_time: 0, difficulty_rate: 0.62, set_type: 1, exam: 0, lock: 0, engine_area: 'shanghai',
    need_redo: false, practice_count: 0,
    structs: [makeStruct('958807', 'Unit 3 Jobs 听说同步', DEMO_CONTENTS.slice(0, 3))],
    contents: DEMO_CONTENTS.slice(0, 3)
  },
  {
    id: '111203419', set_id: '958808', name: '期中听说模拟卷 01',
    set_name: '2026 学年第一学期期中听说模拟卷', first_column_id: '1', first_column_name: '听说模拟',
    column: '期中测试', set_module_id: '4', set_module_name: '考试',
    status: 1, complete: 1, pass: 1, point: 8.6, total_point: 10, avg_point: 86,
    begin: nowSec() - 9 * DAY, end: nowSec() - 2 * DAY, overtime: 0, allow_overtime: 1,
    use_time: 612, difficulty_rate: 0.71, set_type: 1, exam: 0, lock: 0, engine_area: 'shanghai',
    need_redo: false, practice_count: 2,
    structs: [makeStruct('958808', '2026 学年第一学期期中听说模拟卷', DEMO_CONTENTS)],
    contents: DEMO_CONTENTS
  },
  {
    id: '111203420', set_id: '958809', name: 'Unit 2 Strong mind 课文朗读',
    set_name: 'Unit 2 Strong mind 课文朗读', first_column_id: '3', first_column_name: '课文朗读',
    column: '课文', set_module_id: '1', set_module_name: '课文',
    status: 1, complete: 1, pass: 1, point: 9.2, total_point: 10, avg_point: 92,
    begin: nowSec() - 12 * DAY, end: nowSec() - 5 * DAY, overtime: 0, allow_overtime: 1,
    use_time: 305, difficulty_rate: 0.55, set_type: 1, exam: 0, lock: 0, engine_area: 'shanghai',
    need_redo: false, practice_count: 1,
    structs: [makeStruct('958809', 'Unit 2 Strong mind 课文朗读', DEMO_CONTENTS.slice(0, 2))],
    contents: DEMO_CONTENTS.slice(0, 2)
  },
  {
    id: '111203421', set_id: '958810', name: '9年级(上) U1 单元测试',
    set_name: '上海市九年级上 Unit 1 英语听说单元测试', first_column_id: '1', first_column_name: '听说模拟',
    column: '单元测试', set_module_id: '4', set_module_name: '考试',
    status: 0, complete: 0, pass: 0, point: 0, total_point: 10, avg_point: 0,
    begin: nowSec() - 20 * DAY, end: nowSec() - 8 * DAY, overtime: 1, allow_overtime: 0,
    use_time: 0, difficulty_rate: 0.68, set_type: 1, exam: 0, lock: 0, engine_area: 'shanghai',
    need_redo: false, practice_count: 0,
    structs: [makeStruct('958810', '上海市九年级上 Unit 1 英语听说单元测试', DEMO_CONTENTS)],
    contents: DEMO_CONTENTS
  },
  {
    id: '111203422', set_id: '958811', name: '寒假听说专项训练 03',
    set_name: '寒假听说专项训练（三）', first_column_id: '5', first_column_name: '听说专项',
    column: '专项训练', set_module_id: '6', set_module_name: '专项',
    status: 0, complete: 0, pass: 0, point: 0, total_point: 10, avg_point: 0,
    begin: nowSec() - 30 * DAY, end: nowSec() - 10 * DAY, overtime: 1, allow_overtime: 0,
    use_time: 0, difficulty_rate: 0.8, set_type: 1, exam: 0, lock: 0, engine_area: 'shanghai',
    need_redo: false, practice_count: 0,
    structs: [makeStruct('958811', '寒假听说专项训练（三）', DEMO_CONTENTS.slice(4))],
    contents: DEMO_CONTENTS.slice(4)
  }
]

export const MOCK_COLUMNS = [
  { column_id: 1, column_name: '听说模拟', column_set_count: 128, column_set_complete_count: 12, column_score_average: 82, column_set_complete: 0, column_tag: '' },
  { column_id: 2, column_name: '听说专项', column_set_count: 530, column_set_complete_count: 36, column_score_average: 78, column_set_complete: 0, column_tag: '' },
  { column_id: 3, column_name: '读写专项', column_set_count: 378, column_set_complete_count: 8, column_score_average: 75, column_set_complete: 0, column_tag: '' },
  { column_id: 5, column_name: '听力专项', column_set_count: 176, column_set_complete_count: 4, column_score_average: 80, column_set_complete: 0, column_tag: '' }
]

function makeSet(columnId, columnName, setId, name, difficulty, avg) {
  return {
    set_id: setId,
    set_name: name,
    first_column_id: String(columnId),
    first_column_name: columnName,
    set_type: 1,
    set_module_name: '考试',
    difficulty_rate: difficulty,
    avg_point: avg,
    total_point: 10,
    set_score: 10,
    complete: 0,
    set_set_count: DEMO_CONTENTS.length,
    exam_type_list: [],
    contents: DEMO_CONTENTS,
    structs: [makeStruct(setId, name, DEMO_CONTENTS)]
  }
}

export const MOCK_SETS = [
  makeSet(1, '听说模拟', '960001', '上海市九年级上 Unit 2 英语听说模拟卷 01', 0.76, 0),
  makeSet(1, '听说模拟', '960002', '上海市九年级上 Unit 3 英语听说模拟卷 02', 0.72, 0),
  makeSet(1, '听说模拟', '960003', '2026 学年第一学期期中听说模拟卷', 0.71, 86),
  makeSet(2, '听说专项', '960004', '朗读句子专项突破（一）', 0.5, 0),
  makeSet(2, '听说专项', '960005', '交际应答专项突破（二）', 0.58, 0),
  makeSet(2, '听说专项', '960006', '复述与表达专项训练', 0.82, 0),
  makeSet(3, '读写专项', '960007', '阅读理解专项训练（三）', 0.65, 0),
  makeSet(5, '听力专项', '960008', '听力理解专项训练（一）', 0.6, 0)
]

export const MOCK_GRADES = [
  { id: 90329, name: '六年级', resource_id: 363, is_graduate: 0 },
  { id: 5258, name: '七年级', resource_id: 241, is_graduate: 0 },
  { id: 5259, name: '八年级', resource_id: 240, is_graduate: 0 },
  { id: 5260, name: '九年级', resource_id: 239, is_graduate: 1 }
]

export const MOCK_BOOKS = [
  { id: 660, term_name: '上', name: 'SJ', resource_id: 239, display_name: '九年级上', grade_name: '九年级', order: 29 },
  { id: 663, term_name: '下', name: 'SJ', resource_id: 239, display_name: '九年级下', grade_name: '九年级', order: 30 },
  { id: 661, term_name: '上', name: 'SJ', resource_id: 240, display_name: '八年级上', grade_name: '八年级', order: 27 },
  { id: 657, term_name: '下', name: 'SJ', resource_id: 240, display_name: '八年级下', grade_name: '八年级', order: 28 },
  { id: 664, term_name: '上', name: 'SJ(新)', resource_id: 241, display_name: '七年级上', grade_name: '七年级', order: 25 },
  { id: 658, term_name: '下', name: 'SJ', resource_id: 241, display_name: '七年级下', grade_name: '七年级', order: 26 },
  { id: 662, term_name: '上', name: 'SJ', resource_id: 363, display_name: '六年级上', grade_name: '六年级', order: 6461 },
  { id: 659, term_name: '下', name: 'SJ', resource_id: 363, display_name: '六年级下', grade_name: '六年级', order: 6462 }
]

const UNIT_NAMES = [
  [20610, 'Unit 1 Trying new things'],
  [20611, 'Unit 2 Strong mind'],
  [20712, 'Unit 3 Jobs'],
  [20713, 'Unit 4 Smart home'],
  [20856, 'Unit 5 Films'],
  [20857, 'Unit 6 Mountains and rivers'],
  [20658, 'Starter'],
  [27357, 'Culture corner'],
  [27358, 'Literature corner']
]

export const MOCK_UNITS = UNIT_NAMES.map(([id, name], i) => ({
  unit_id: id,
  unit_name: name,
  unit_order: i + 1,
  unit_code: '0',
  unit_is_lock: 0,
  unit_set_count: [53, 41, 36, 28, 22, 18, 9, 6, 4][i],
  unit_set_complete_count: 0,
  unit_set_complete: 0,
  unit_score_average: 0,
  level: 0
}))

export function mockModules(unitId) {
  const unit = MOCK_UNITS.find((u) => String(u.unit_id) === String(unitId)) || MOCK_UNITS[0]
  const names = ['课文', '词汇·PK', '听说同步', '读写同步', '听力同步']
  return {
    data: names.map((name, i) => ({
      module_id: 100 + i,
      module_name: name,
      module_order: i,
      module_is_lock: 0,
      module_tag: '',
      module_tag_type: 1,
      module_set_count: [53, 41, 4, 1, 1][i],
      module_set_complete: 0,
      module_set_complete_count: 0,
      module_score_average: 0,
      composition_correct_status: 0,
      is_credential_resource: i === 0 ? 1 : 0,
      source: i === 0 ? 1 : 0,
      module_set_complete_infos: [],
      module_set_infos: [{ set_type: 1, set_ids: [801749 + i * 17, 801750 + i * 17, 801751 + i * 17] }]
    })),
    unit_code: '07030109419-7332-' + unitId,
    book_code: '07030109419-7332',
    level: 1,
    sync_text_show_cn: 0,
    sn: 'test'
  }
}

export const MOCK_MISTAKE_SUMMARY = {
  to_correct_count: { audio: 9, read_write: 2 },
  corrected_count: { audio: 3, read_write: 1 }
}

export const MOCK_MISTAKES = [
  { id: 'mk1', set_id: '958806', entity_id: '900101', set_name: '上海市九年级上 Unit 2 英语听说模拟卷 01', group_name: '朗读句子', content: 'excuse me', score: 1.2, full_score: 2.5, corrected: 0, type: 'audio', create_time: '2026-11-06 18:20', answer: 'excuse me', analyze: '注意 /ɪkˈskjuːz/ 的重音位置。' },
  { id: 'mk2', set_id: '958806', entity_id: '900102', set_name: '上海市九年级上 Unit 2 英语听说模拟卷 01', group_name: '朗读句子', content: 'a good reason', score: 1.6, full_score: 2.5, corrected: 0, type: 'audio', create_time: '2026-11-06 18:22', answer: 'a good reason', analyze: 'reason 的元音 /ˈriːzn/ 需饱满。' },
  { id: 'mk3', set_id: '958808', entity_id: '900104', set_name: '2026 学年第一学期期中听说模拟卷', group_name: '交际应答', content: 'Could you tell me how to get to the library?', score: 3.1, full_score: 5, corrected: 0, type: 'audio', create_time: '2026-11-05 10:02', answer: 'Go straight and turn left at the second crossing.', analyze: '问路应答要点：方向 + 参照物。' },
  { id: 'mk4', set_id: '958808', entity_id: '900105', set_name: '2026 学年第一学期期中听说模拟卷', group_name: '复述', content: 'Retell the story about a brave boy.', score: 4.2, full_score: 7.5, corrected: 0, type: 'audio', create_time: '2026-11-05 10:15', answer: 'The boy helped his neighbour out of the fire.', analyze: '复述需覆盖时间、人物、事件、结果四要素。' },
  { id: 'mk5', set_id: '960007', entity_id: 'rw1', set_name: '阅读理解专项训练（三）', group_name: '阅读理解', content: 'What is the main idea of the passage?', score: 0, full_score: 5, corrected: 1, type: 'read_write', create_time: '2026-11-03 20:10', answer: 'B', analyze: '主旨题关注首段与末段主题句。' }
]

export function mockHomeworkDetail(id) {
  const found = MOCK_HOMEWORK.find((h) => String(h.id) === String(id))
  if (found) return found
  const base = MOCK_HOMEWORK[0]
  return { ...base, id: String(id), name: '演示作业 ' + id }
}

// ---------------------------------------------------------------------------
// content 包（collector.read / dialogue / picture）
// ---------------------------------------------------------------------------
const MOCK_CONTENTS = {
  900101: {
    structure_type: 'collector.read',
    info: {
      value: 'excuse me',
      analyze: '1. excuse me<br>2. a good reason<br>3. improve your handwriting',
      translate: '打扰一下；请再说一遍',
      symbol: '',
      stid: '900101',
      audio: 'content.mp3',
      image: '',
      video: '',
      ai: ''
    }
  },
  900102: {
    structure_type: 'collector.read',
    info: {
      value: 'The library is on the second floor.',
      analyze: '注意 library /ˈlaɪbrəri/ 与 second /ˈsekənd/ 的读音。',
      translate: '图书馆在二楼。',
      symbol: '',
      stid: '900102',
      audio: 'content.mp3',
      image: '',
      video: '',
      ai: ''
    }
  },
  900103: {
    structure_type: 'collector.read',
    info: {
      value: 'Would you mind opening the window?',
      analyze: 'Would you mind doing sth.? 表示委婉请求，语调用升调。',
      translate: '你介意开一下窗户吗？',
      symbol: '',
      stid: '900103',
      audio: 'content.mp3',
      image: '',
      video: '',
      ai: ''
    }
  },
  900104: {
    structure_type: 'collector.dialogue',
    info: {
      value: 'Listen and respond to the question.',
      ask: '1. <p>Could you tell me how to get to the library?</p>',
      askaudio: 'ques1askaudio.mp3',
      answer: 'Go straight and turn left at the second crossing.',
      analyze: '问路应答需给出方向与参照物，可用 Go straight / Turn left / It is next to… 等表达。',
      question: [
        {
          std: [
            { value: 'Go straight and turn left at the second crossing.', ai: '', audio: '' },
            { value: 'Walk along this road, and it is on your left.', ai: '', audio: '' }
          ],
          ref: '',
          ask: 'Could you tell me how to get to the library?',
          answer: 'Go straight and turn left at the second crossing.',
          askaudio: 'ques1askaudio.mp3',
          aswaudio: '',
          xh: '1',
          sucai: '',
          keywords: 'go straight|turn left|library',
          role: ''
        }
      ],
      image: '',
      stid: '900104',
      audio: ''
    }
  },
  900105: {
    structure_type: 'collector.picture',
    info: {
      value: 'Look at the pictures and retell the story in your own words.',
      std: [
        { value: 'Last Sunday, a little boy saw smoke coming from his neighbour’s kitchen. He called 119 at once and told the firemen the address. Soon the fire was put out and nobody was hurt.', ai: '', audio: '' }
      ],
      ref: 'Last Sunday / smoke / call 119 / put out / nobody hurt',
      keypoint: '时间 · 人物 · 事件 · 结果',
      image: 'content.jpg',
      analyze: '复述需覆盖四要素，并使用一般过去时串联事件。',
      topic: 'A brave boy',
      stid: '900105',
      audio: ''
    }
  },
  900106: {
    structure_type: 'collector.picture',
    info: {
      value: 'Talk about the picture and give your opinion on helping others.',
      std: [
        { value: 'In the picture, a student is helping an old man cross the street. In my opinion, we should always be ready to help others, because a small act of kindness can make a big difference.', ai: '', audio: '' }
      ],
      ref: '',
      keypoint: '描述画面 + 表达观点 + 给出理由',
      image: 'content.jpg',
      analyze: '话题表述建议按“描述—观点—理由—总结”四步组织语言。',
      topic: 'Helping others',
      stid: '900106',
      audio: ''
    }
  }
}

export function getMockContent(stid) {
  const key = String(stid || '')
  if (MOCK_CONTENTS[key]) return MOCK_CONTENTS[key]
  // 任意 stid：按最后一位数字稳定映射到 3 种题型之一
  const idx = Number(key.replace(/\D/g, '').slice(-1) || 0) % 3
  const kinds = ['collector.read', 'collector.dialogue', 'collector.picture']
  const kind = kinds[idx]
  if (kind === 'collector.dialogue') return { ...MOCK_CONTENTS[900104], info: { ...MOCK_CONTENTS[900104].info, stid: key } }
  if (kind === 'collector.picture') return { ...MOCK_CONTENTS[900105], info: { ...MOCK_CONTENTS[900105].info, stid: key } }
  return { ...MOCK_CONTENTS[900101], info: { ...MOCK_CONTENTS[900101].info, stid: key } }
}

// ---------------------------------------------------------------------------
// 简单确定性 hash（仅 mock 签名/uid 用）
// ---------------------------------------------------------------------------
export function fakeHash32(str) {
  let h1 = 0x811c9dc5
  let h2 = 0x1000193
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i)
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0
    h2 = Math.imul(h2 + c, 0x85ebca6b) >>> 0
  }
  const a = h1.toString(16).padStart(8, '0')
  const b = h2.toString(16).padStart(8, '0')
  const c = (Math.imul(h1, 0x9e3779b1) >>> 0).toString(16).padStart(8, '0')
  const d = (Math.imul(h2 ^ h1, 0xc2b2ae35) >>> 0).toString(16).padStart(8, '0')
  return (a + b + c + d).slice(0, 32)
}

function b64EncodeUtf8(str) {
  return btoa(unescape(encodeURIComponent(str)))
}

function b64DecodeUtf8(b64) {
  try {
    return decodeURIComponent(escape(atob(b64)))
  } catch {
    return ''
  }
}

// 从 api.js 组装的请求信封中取出业务 params（body 是 base64 的 [{r,params}]）
function decodedParams(body) {
  try {
    const env = JSON.parse(body || '{}')
    if (env && typeof env.body === 'string') {
      const arr = JSON.parse(b64DecodeUtf8(env.body))
      return (Array.isArray(arr) && arr[0] && arr[0].params) || {}
    }
    if (Array.isArray(env)) return (env[0] && env[0].params) || {}
    return env.params || env
  } catch {
    return {}
  }
}

// mock「加密」：XOR + base64，仅用于让登录链路的字段形态接近真实
const MOCK_AES_KEY = 'k_serves'
function mockEncrypt(plain) {
  const s = String(plain ?? '')
  let out = ''
  for (let i = 0; i < s.length; i++) {
    out += String.fromCharCode(s.charCodeAt(i) ^ MOCK_AES_KEY.charCodeAt(i % MOCK_AES_KEY.length))
  }
  return b64EncodeUtf8(out)
}

function mockDecrypt(b64) {
  const s = b64DecodeUtf8(b64)
  let out = ''
  for (let i = 0; i < s.length; i++) {
    out += String.fromCharCode(s.charCodeAt(i) ^ MOCK_AES_KEY.charCodeAt(i % MOCK_AES_KEY.length))
  }
  return out
}

// ---------------------------------------------------------------------------
// mock media_url：现场合成一段 1.2s 提示音 WAV，避免依赖外网 CDN
// ---------------------------------------------------------------------------
let beepUrl = null
function makeBeepUrl() {
  if (beepUrl) return beepUrl
  const sampleRate = 16000
  const seconds = 1.2
  const total = Math.floor(sampleRate * seconds)
  const dataSize = total * 2
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)
  const writeStr = (offset, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, dataSize, true)
  for (let i = 0; i < total; i++) {
    const t = i / sampleRate
    const env = Math.min(1, t * 12) * Math.min(1, (seconds - t) * 6)
    const sample = Math.sin(2 * Math.PI * 660 * t) * 0.22 * env
    view.setInt16(44 + i * 2, Math.round(sample * 32767), true)
  }
  beepUrl = URL.createObjectURL(new Blob([buffer], { type: 'audio/wav' }))
  return beepUrl
}

// ---------------------------------------------------------------------------
// mock HTTP
// ---------------------------------------------------------------------------
function routeOf(url) {
  try {
    const u = new URL(String(url))
    return u.pathname.replace(/^\/+/, '')
  } catch {
    return String(url || '').replace(/^https?:\/\/[^/]+/, '').replace(/^\/+/, '')
  }
}

function homeworkBody() {
  const todo = MOCK_HOMEWORK.filter((h) => h.status === 0 && !h.overtime)
  const overdue = MOCK_HOMEWORK.filter((h) => h.overtime === 1)
  return {
    all_count: MOCK_HOMEWORK.length,
    to_do_count: todo.length,
    to_overtime_count: overdue.length,
    read_write: [],
    current_class_id: 1155123,
    data: JSON.parse(JSON.stringify(MOCK_HOMEWORK)),
    base_url: 'https://cdnsubject.ets100.com/made/',
    homework_privilege: 0,
    server_datetime: nowSec()
  }
}

function mockHttpResponse(url, body) {
  const route = routeOf(url)
  const path = route.toLowerCase()
  let data

  if (path === 'user/login' || path === 'user/register-or-login') {
    let parsed = {}
    try { parsed = JSON.parse(body || '{}') } catch { parsed = {} }
    void parsed
    data = {
      token: 'mock-token-' + fakeHash32(String(Date.now())).slice(0, 24),
      expire: nowSec() + 14 * DAY,
      recent_account_id: MOCK_PROFILE.recent_account_id,
      user_type: 0,
      name: MOCK_PROFILE.name,
      phone: MOCK_PROFILE.phone,
      raw_phone: MOCK_PROFILE.raw_phone,
      newUser: false,
      partner: 'common'
    }
  } else if (path === 'user/info') {
    data = { ...MOCK_PROFILE }
  } else if (path === 'user/logout') {
    data = { ok: true }
  } else if (path === 'g/homework/list') {
    data = homeworkBody()
  } else if (path === 'm/homework/info' || path === 'g/homework/info') {
    const params = decodedParams(body)
    data = mockHomeworkDetail(params.homework_id || params.set_id || '111203417')
  } else if (path === 'm/mistake/summary') {
    data = { ...MOCK_MISTAKE_SUMMARY }
  } else if (path === 'm/mistake/list') {
    data = { data: MOCK_MISTAKES, pagination: { total_count: MOCK_MISTAKES.length, page: 1, limit: 20 } }
  } else if (path === 'm/ecard/list') {
    data = { data: MOCK_ECARDS }
  } else if (path === 'g/set/column-v2' || path === 'm/set/column') {
    data = { data: MOCK_COLUMNS }
  } else if (path === 'g/set/list' || path === 'g/set/list-v2') {
    const params = decodedParams(body)
    const columnId = params.column_id
    const list = columnId ? MOCK_SETS.filter((s) => String(s.first_column_id) === String(columnId)) : MOCK_SETS
    data = { data: list, pagination: { total_count: list.length, page: 1, limit: 20 } }
  } else if (path === 'g/set/unit-list') {
    data = { data: MOCK_UNITS, pagination: { total_count: MOCK_UNITS.length, page: 1, limit: 20 }, word_source: 0, count: 0, book_code: '' }
  } else if (path === 'g/set/unit-info') {
    const params = decodedParams(body)
    const unit = MOCK_UNITS.find((u) => String(u.unit_id) === String(params.unit_id)) || MOCK_UNITS[0]
    data = { data: unit }
  } else if (path === 'g/set/module-list') {
    const params = decodedParams(body)
    data = mockModules(params.unit_id)
  } else if (path === 'g/resource/grade-list') {
    data = { grades: MOCK_GRADES }
  } else if (path === 'g/resource/book-list') {
    data = { books: MOCK_BOOKS }
  } else if (path === 'm/advertisement/list') {
    data = { advertisement: [] }
  } else if (path === 'system/config') {
    data = {
      stic_record_enable_speex: '0',
      pc_force_record_vol_100: '0',
      pc_min_record_volume: '80',
      pc_web_enable_aimix: '1',
      mock: '1'
    }
  } else if (path === 'announcement/list') {
    data = { title: '', detail: '' }
  } else if (path === 'system/time') {
    data = { date: new Date().toISOString().slice(0, 19).replace('T', ' '), time_stamp: nowSec() }
  } else if (path === 'g/data/sls-config' || path === 'p1/student/ability/sls/slsAppConfig') {
    data = { mock: true, access_key_id: '', security_token: '', project: 'mock', logstore: 'mock' }
  } else {
    data = { mock: true, route }
  }

  const payload = [{ msg: '成功', code: 0, body: data }]
  return { status: 200, body: JSON.stringify(payload), headers: { 'content-type': 'application/json', 'x-mock': '1' } }
}

// ---------------------------------------------------------------------------
// mockInvoke：模拟插件返回（data 一律为 JSON 字符串，与原生桥语义一致）
// ---------------------------------------------------------------------------
function asJson(obj) {
  return JSON.stringify(obj)
}

function mockFileRead(filePath) {
  const p = String(filePath || '')
  if (/content2?\.json$/i.test(p)) {
    const m = p.match(/(\d{5,})/)
    return asJson({ content: JSON.stringify(getMockContent(m ? m[1] : '900101')) })
  }
  if (/info\.json$/i.test(p)) return asJson({ content: '[]' })
  if (/res\.json$/i.test(p)) return asJson({ content: '{"set_score":"10"}' })
  return asJson({ content: '{}' })
}

export async function mockInvoke(plugin, action, args) {
  const p = String(plugin || '')
  const a = String(action || '')
  let parsed = {}
  try {
    parsed = typeof args === 'string' ? (args ? JSON.parse(args) : {}) : (args || {})
  } catch { parsed = {} }

  if (p === '__core') {
    if (a === 'info') {
      return asJson({
        appDir: 'C:\\ets-replica',
        dataDir: 'C:\\Users\\Demo\\AppData\\Roaming\\ETS-Replica',
        cacheDir: 'C:\\Users\\Demo\\AppData\\Roaming\\ETS-Replica\\cache',
        homeUrl: 'http://127.0.0.1/',
        version: '5.7.9',
        mock: true
      })
    }
    if (a === 'media_url') return asJson({ url: makeBeepUrl() })
    if (a === 'log') return asJson({ ok: true })
    if (a === 'open_external') return asJson({ ok: true })
    return asJson({ code: -2, msg: 'not implemented' })
  }

  if (p === 'EtsHelper') {
    if (a === 'aes_ecb_encrypt') return asJson({ b64: mockEncrypt(parsed.plain) })
    if (a === 'aes_ecb_decrypt') return asJson({ plain: mockDecrypt(parsed.b64) })
    if (a === 'encode_api_body_v2') {
      const body = String(parsed.body || '')
      const time = String(parsed.time || '')
      return asJson({ pid: 'pcWin', key_id: '202608', sign: fakeHash32('pcWin' + time + body + 'mock-key-v2'), sign_version: '2' })
    }
    if (a === 'encode_api_body') {
      return asJson(fakeHash32('grlx' + String(parsed.time || '') + String(parsed.body || '') + 'mock-key-v1'))
    }
    if (a === 'encode_api_resp_v2') {
      return asJson({ pid: 'pcWin', key_id: '202608', sign: fakeHash32('pcWin' + String(parsed.response || '') + 'mock'), sign_version: '2' })
    }
    if (a === 'get_appdata_path') return asJson('C:\\Users\\Demo\\AppData\\Roaming')
    if (a === 'log_data') return asJson({ ok: true })
    if (a === 'check_update' || a === 'check_update_force') return asJson({ rncode: 0, rnmsg: 'no newer version' })
    if (a === 'init') return asJson({ ok: true })
    return asJson({ code: -2, msg: 'not implemented' })
  }

  if (p === 'HttpHelper') {
    if (a === 'request') {
      return asJson(mockHttpResponse(parsed.url, parsed.body))
    }
    if (a === 'download') {
      const stid = (String(parsed.filePath || '').match(/(\d{5,})/) || [])[1] || '900101'
      return asJson({ code: 0, filePath: `C:\\Users\\Demo\\AppData\\Roaming\\ETS-Replica\\cache\\mock_${stid}.zip`, size: 102400, mock: true })
    }
    if (a === 'downloadresource' || a === 'downloadsdk' || a === 'upload') {
      return asJson({ code: 0, msg: 'mock ok' })
    }
    if (a === 'monitornetspeed') return asJson({ kbps: 20480 })
    if (a === 'isrpkexist') return asJson({ result: true })
    return asJson({ code: -2, msg: 'not implemented' })
  }

  if (p === 'FileHelper') {
    if (a === 'readfile') return mockFileRead(parsed.filePath)
    if (a === 'readbinaryfile' || a === 'getbase64') return asJson({ base64: '' })
    if (a === 'writefile' || a === 'writefilewithbinary' || a === 'deletefileordirectory' || a === 'createfolder' || a === 'copyfileordirectory' || a === 'removefiletootherpath') return asJson({ code: 0 })
    if (a === 'existfileorfolder') return asJson({ result: true, size: 1024 })
    if (a === 'getmd5') return asJson({ md5: fakeHash32(String(parsed.filePath || '')) })
    if (a === 'getfoledersize') return asJson({ errorCode: 0, errorMsg: 'get dir size ok', size: 1024 * 1024 })
    return asJson({ code: -2, msg: 'not implemented' })
  }

  if (p === 'SevenZip') {
    if (a === 'unzip') return asJson({ code: 0, files: 2 })
    if (a === 'zip') return asJson({ code: 0, files: 1 })
    return asJson({ code: -2, msg: 'not implemented' })
  }

  if (p === 'SQLitePln' || p === 'sqlitepln') {
    if (a === 'execQuery') return asJson({ rows: [] })
    if (a === 'execDML') return asJson({ changes: 0 })
    return asJson({ code: 0 })
  }

  if (p === 'ShellHelper') {
    if (a === 'getpcinfo') return asJson(MOCK_DEVICE)
    if (a === 'getconfig') return asJson({ suspensionBallPort: 40001, mock: true })
    if (a === 'getuniqueid') return asJson({ id: 'MOCK-DEVICE-0001' })
    if (a === 'checkadapter') return asJson({ rncode: 1, rnmsg: '网卡正常.' })
    if (a === 'getvolume') return asJson({ volume: 80 })
    if (a === 'setvolume' || a === 'setmute') return asJson({ code: 0 })
    if (a === 'processexist') return asJson({ result: false })
    if (a === 'startprocess' || a === 'stopprocess') return asJson({ code: 0 })
    if (a === 'netcheck') return asJson({ normal: true })
    if (a === 'getroomid') return asJson({ roomid: '' })
    return asJson({ code: -2, msg: 'not implemented' })
  }

  if (p === 'SysConfig') {
    if (a === 'init') return asJson({ ok: true })
    return asJson({ code: -2, msg: 'not implemented' })
  }

  if (p === 'appcontroller') {
    return asJson({ code: 0, mock: true })
  }

  return asJson({ code: -2, msg: 'mock: not implemented (' + p + '.' + a + ')' })
}
