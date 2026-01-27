import React, { useState, useEffect } from 'react';
import {
  Layout, Table, Tag, Space, Card, Statistic, Row, Col,
  Form, Select, Slider, Button, Drawer, Typography, Descriptions,
  List, Badge, ConfigProvider, theme, DatePicker, Spin
} from 'antd';
import dayjs from 'dayjs';
import {
  UserOutlined, DashboardOutlined, FilterOutlined,
  ReloadOutlined, RiseOutlined, RocketTwoTone, ArrowLeftOutlined,
  PlayCircleTwoTone, CheckCircleTwoTone, MenuFoldOutlined, MenuUnfoldOutlined
} from '@ant-design/icons';
import { getUsers, getStats, getFilters, getUser } from './services/api';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts';

const { RangePicker } = DatePicker;

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;
const { Option } = Select;

const App = () => {
  // State
  // Global State (driven by Pie Chart)
  const [globalCategory, setGlobalCategory] = useState(null);
  const [dateRange, setDateRange] = useState(null);

  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [chartsLoading, setChartsLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [filterOptions, setFilterOptions] = useState({});
  const [filters, setFilters] = useState({ page: 1, limit: 10, min_score: 1 });

  // Drawer State
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);

  const [collapsed, setCollapsed] = useState(false);



  // Initial Load
  useEffect(() => {
    loadInitData();
  }, []);

  // ... (rest of useEffects)

  // ... (rest of functions)

  // (This is just context, I will scroll down to render to replace Sider)


  // Reload users when filters change
  useEffect(() => {
    fetchUserData();
  }, [filters]);

  const loadInitData = async () => {
    try {
      // Initial range 2025-10-01 to 2026-01-27 as requested defaults or empty
      const [s, f] = await Promise.all([getStats(), getFilters()]);
      setStats(s);
      setFilterOptions(f);
    } catch (e) {
      console.error(e);
    }
  };

  // Function to reload stats with date filter
  // Function to reload stats with date and global category filter
  // Function to reload stats with date and global category filter
  const fetchStats = async (dates, category) => {
    setChartsLoading(true);
    try {
      const params = {};
      if (dates) {
        params.start_date = dates[0].toISOString();
        params.end_date = dates[1].toISOString();
      }
      if (category) {
        params.category = category;
      }
      const s = await getStats(params);
      setStats(s);
    } catch (e) { console.error(e); }
    finally { setChartsLoading(false); }
  };

  const onGlobalCategorySelect = (category) => {
    if (globalCategory === category) {
      // Deselect
      setGlobalCategory(null);
      // Reset stats to show all (respecting time)
      fetchStats(dateRange, null);
      // Reset table filter
      setFilters(prev => {
        const next = { ...prev, page: 1 };
        delete next.category;
        return next;
      });
    } else {
      // Select
      setGlobalCategory(category);
      // Filter stats (industries, counts) by this category
      fetchStats(dateRange, category);
      // Filter table
      setFilters(prev => ({ ...prev, category, page: 1 }));
    }
    // Reset subcategory view in Pie (optional, user might want to stay drilled down?)
    // For now, let's reset subcategory view if switching major category
    if (selectedCategory && selectedCategory !== category) setSelectedCategory(null);
  };

  const fetchUserData = async () => {
    setLoading(true);
    try {
      // Pass filters including date range and global category
      const params = { ...filters };
      if (dateRange) {
        params.start_date = dateRange[0].toISOString();
        params.end_date = dateRange[1].toISOString();
      }
      // Global category overrides form category if present (or syncs with it)
      if (globalCategory) params.category = globalCategory;

      const data = await getUsers(params);
      setUsers(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (changedValues) => {
    setFilters(prev => ({ ...prev, ...changedValues, page: 1 }));
  };

  const handleTableChange = (pagination, f, sorter) => {
    setFilters(prev => ({
      ...prev,
      page: pagination.current,
      limit: pagination.pageSize,
      sort_by: sorter.field || 'business_potential.score',
      sort_order: sorter.order === 'ascend' ? 'asc' : 'desc'
    }));
  };

  const showDrawer = async (record) => {
    setDrawerVisible(true);
    setDrawerLoading(true);
    try {
      const fullUser = await getUser(record.user_id);
      setSelectedUser(fullUser);
    } catch (e) {
      console.error(e);
    } finally {
      setDrawerLoading(false);
    }
  };

  // Columns
  const columns = [
    {
      title: 'Email',
      dataIndex: 'user_email',
      key: 'user_email',
      render: (text) => <Text strong style={{ color: '#1890ff' }}>{text}</Text>,
    },
    {
      title: 'Industry',
      dataIndex: ['ai_profile', 'positioning', 'industry'],
      key: 'industry',
    },
    {
      title: 'Platform',
      dataIndex: ['ai_profile', 'positioning', 'platform'],
      key: 'platform',
      render: (text) => <Tag color="blue">{text}</Tag>
    },
    {
      title: 'Potential Score',
      dataIndex: ['ai_profile', 'business_potential', 'score'],
      key: 'business_potential.score',
      sorter: true,
      render: (score) => {
        let color = score >= 8 ? 'green' : score >= 5 ? 'orange' : 'red';
        return <Tag color={color} style={{ fontWeight: 'bold' }}>{score}/10</Tag>;
      }
    },
    {
      title: 'Stage',
      dataIndex: ['ai_profile', 'business_potential', 'stage'],
      key: 'stage',
    },
    {
      title: 'Total Runs',
      dataIndex: ['stats', 'total_runs'],
      key: 'stats.total_runs',
      sorter: true,
      render: (val, record) => val || record.stats?.total_runs_30d || 0
    },
    {
      title: 'Active Days',
      dataIndex: ['stats', 'active_days'],
      key: 'stats.active_days',
      sorter: true,
      render: (val, record) => `${val || record.stats?.active_days_30d || 0} days`
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Button type="primary" size="small" onClick={() => showDrawer(record)}>
          Detail
        </Button>
      ),
    },

  ];

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#722ed1', // Vivid Purple
          colorBgLayout: '#f0f2f5',
          borderRadius: 8,
        },
        components: {
          Layout: {
            colorBgHeader: '#fff',
          },
          Card: {
            boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
          }
        }
      }}
    >
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px',
          background: 'linear-gradient(90deg, #fff 0%, #f9f0ff 100%)',
          boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
          zIndex: 10,
          borderBottom: '1px solid #f0f0f0'
        }}>
          <RocketTwoTone twoToneColor="#722ed1" style={{ fontSize: '28px', marginRight: '12px' }} />
          <Title level={3} style={{ margin: 0, background: 'linear-gradient(45deg, #722ed1, #1890ff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            User Insights
          </Title>
        </Header>

        <Layout>
          <Sider
            width={300}
            theme='light'
            collapsible
            collapsed={collapsed}
            onCollapse={setCollapsed}
            trigger={null}
            collapsedWidth={80}
            style={{
              padding: '24px 12px',
              background: 'rgba(255, 255, 255, 0.6)',
              backdropFilter: 'blur(20px)',
              borderRight: '1px solid rgba(0,0,0,0.03)',
              transition: 'all 0.2s'
            }}
          >
            <div style={{ display: 'flex', justifyContent: collapsed ? 'center' : 'space-between', alignItems: 'center', marginBottom: 24 }}>
              {!collapsed && <Title level={4} style={{ margin: 0, fontWeight: 300 }}><FilterOutlined /> Filters</Title>}
              <Button
                type="text"
                icon={collapsed ? <FilterOutlined style={{ fontSize: 18 }} /> : <MenuFoldOutlined />}
                onClick={() => setCollapsed(!collapsed)}
                title={collapsed ? "Expand Filters" : "Collapse Filters"}
              />
            </div>

            <div style={{ display: collapsed ? 'none' : 'block' }}>
              <Form layout="vertical" onValuesChange={(changed, all) => {
                if (changed.dateRange) {
                  setDateRange(changed.dateRange);
                  fetchStats(changed.dateRange, globalCategory);
                }
                handleFilterChange(changed);
              }}>
                <Form.Item label="Date Range" name="dateRange">
                  <RangePicker style={{ width: '100%' }} />
                </Form.Item>

                <Form.Item label="Min Potential Score" name="min_score" initialValue={1}>
                  <Slider min={1} max={10} marks={{ 1: '1', 5: '5', 10: '10' }} />
                </Form.Item>

                <Form.Item label="User Category" name="category">
                  <Select allowClear placeholder="Select Category" style={{ width: '100%' }}>
                    {filterOptions.categories?.map(c => <Option key={c} value={c}>{c}</Option>)}
                  </Select>
                </Form.Item>

                <Form.Item label="Industry" name="industry">
                  <Select allowClear placeholder="Select Industry">
                    {filterOptions.industries?.map(i => <Option key={i} value={i}>{i}</Option>)}
                  </Select>
                </Form.Item>

                <Form.Item label="Platform" name="platform">
                  <Select allowClear placeholder="Select Platform">
                    {filterOptions.platforms?.map(p => <Option key={p} value={p}>{p}</Option>)}
                  </Select>
                </Form.Item>

                <Form.Item label="Stage" name="stage">
                  <Select allowClear placeholder="Select Stage">
                    {filterOptions.stages?.map(s => <Option key={s} value={s}>{s}</Option>)}
                  </Select>
                </Form.Item>
              </Form>
            </div>
            {collapsed && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, marginTop: 24 }}>
                <Tooltip title="Expand to filter" placement="right">
                  <FilterOutlined style={{ fontSize: 24, color: '#bfbfbf' }} />
                </Tooltip>
              </div>
            )}
          </Sider>

          <Content style={{ padding: '24px', overflowY: 'auto', background: '#f5f7fa' }}>
            {/* Dashboard Stats */}
            {stats && (
              <Spin spinning={chartsLoading}>
                <Row gutter={16} style={{ marginBottom: '24px' }}>
                  <Col span={6}>
                    <Card hoverable>
                      <Statistic
                        title={globalCategory ? `Total Users (${globalCategory})` : "Total Users"}
                        value={stats.total_users}
                        prefix={<UserOutlined style={{ color: '#1890ff' }} />}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card hoverable>
                      <Statistic
                        title="High Potential (>7)"
                        value={stats.high_potential_count}
                        valueStyle={{ color: '#3f8600' }}
                        prefix={<RiseOutlined />}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card hoverable>
                      <Statistic
                        title="Top Industry"
                        value={stats.industries ? Object.keys(stats.industries)[0] : '-'}
                        prefix={<RocketTwoTone twoToneColor="#eb2f96" />}
                      />
                    </Card>
                  </Col>
                </Row>

                {/* Analytical Charts */}
                <Row gutter={16} style={{ marginBottom: '24px' }}>
                  {/* 1. Category Pie Chart (The Controller) */}
                  <Col span={8}>
                    <Card
                      title={
                        selectedCategory ? (
                          <Space>
                            <Button type="text" icon={<ArrowLeftOutlined />} onClick={(e) => { e.stopPropagation(); setSelectedCategory(null); }} />
                            {selectedCategory}
                          </Space>
                        ) : "User Category Distribution"
                      }
                      extra={!selectedCategory && <Text type="secondary" style={{ fontSize: 12 }}>Click Slice to Filter</Text>}
                      style={{ height: 400, border: globalCategory ? '2px solid #722ed1' : undefined }}
                    >
                      {stats.categories ? (
                        <ResponsiveContainer width="100%" height={330}>
                          <PieChart>
                            <Pie
                              data={
                                selectedCategory && stats.categories[selectedCategory]
                                  ? Object.entries(stats.categories[selectedCategory].subcategories).map(([name, value]) => ({ name, value }))
                                  : Object.entries(stats.categories).map(([name, data]) => ({ name, value: data.count }))
                              }
                              cx="50%"
                              cy="40%"
                              innerRadius={60}
                              outerRadius={80}
                              fill="#1890ff"
                              paddingAngle={5}
                              dataKey="value"
                              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                              onClick={(data) => {
                                // Disable subcategory clicking as requested
                                if (selectedCategory) return;
                                onGlobalCategorySelect(data.name);
                                setSelectedCategory(data.name);
                              }}
                              style={{ cursor: selectedCategory ? 'default' : 'pointer' }}
                            >
                              {/* Custom Cells */}
                              {(selectedCategory && stats.categories[selectedCategory]
                                ? Object.entries(stats.categories[selectedCategory].subcategories).map(([n, _]) => n)
                                : Object.entries(stats.categories).map(([n, _]) => n)
                              ).map((name, index) => (
                                <Cell
                                  key={`cell-${index}`}
                                  fill={['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#EFDB50', '#ff85c0'][index % 7]}
                                  stroke={globalCategory === name ? '#722ed1' : '#fff'}
                                  strokeWidth={globalCategory === name ? 3 : 2}
                                />
                              ))}
                            </Pie>
                            <Tooltip />
                            <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '10px' }} />
                          </PieChart>
                        </ResponsiveContainer>
                      ) : <Text type="secondary">No category data yet.</Text>}
                    </Card>
                  </Col>

                  {/* 2. Payment Rate Chart (Line) */}
                  <Col span={8}>
                    <Card title="Payment Conversion Rate" style={{ height: 400 }}>
                      {stats.payment_stats && (
                        <ResponsiveContainer width="100%" height={330}>
                          <LineChart
                            data={Object.entries(stats.payment_stats)
                              .map(([name, data]) => ({ name, rate: data.rate, paid: data.paid, total: data.total }))
                              .sort((a, b) => b.rate - a.rate)
                            }
                            margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" style={{ fontSize: '10px' }} interval={0} angle={-45} textAnchor="end" height={60} />
                            <YAxis unit="%" />
                            <Tooltip
                              content={({ active, payload, label }) => {
                                if (active && payload && payload.length) {
                                  const data = payload[0].payload;
                                  return (
                                    <div style={{ background: '#fff', padding: 10, border: '1px solid #ccc', borderRadius: 4 }}>
                                      <p style={{ fontWeight: 'bold', marginBottom: 4 }}>{label}</p>
                                      <p style={{ color: '#8884d8', marginBottom: 4 }}>Conversion Rate: {data.rate}%</p>
                                      <p style={{ fontSize: 12, color: '#666', margin: 0 }}>
                                        Paid Users: {data.paid}<br />
                                        Total Users: {data.total}
                                      </p>
                                    </div>
                                  );
                                }
                                return null;
                              }}
                            />
                            <Line type="monotone" dataKey="rate" stroke="#8884d8" name="Conversion Rate" strokeWidth={2} />
                          </LineChart>
                        </ResponsiveContainer>
                      )}
                    </Card>
                  </Col>

                  {/* 3. Payment Intent Rate Chart (Line) */}
                  <Col span={8}>
                    <Card title="Payment Intent Rate" style={{ height: 400 }}>
                      {stats.payment_stats && (
                        <ResponsiveContainer width="100%" height={330}>
                          <LineChart
                            data={Object.entries(stats.payment_stats)
                              .map(([name, data]) => ({ name, rate: data.intent_rate, intent: data.intent, total: data.total }))
                              .sort((a, b) => b.rate - a.rate)
                            }
                            margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" style={{ fontSize: '10px' }} interval={0} angle={-45} textAnchor="end" height={60} />
                            <YAxis unit="%" />
                            <Tooltip
                              content={({ active, payload, label }) => {
                                if (active && payload && payload.length) {
                                  const data = payload[0].payload;
                                  return (
                                    <div style={{ background: '#fff', padding: 10, border: '1px solid #ccc', borderRadius: 4 }}>
                                      <p style={{ fontWeight: 'bold', marginBottom: 4 }}>{label}</p>
                                      <p style={{ color: '#82ca9d', marginBottom: 4 }}>Intent Rate: {data.rate}%</p>
                                      <p style={{ fontSize: 12, color: '#666', margin: 0 }}>
                                        Intent Users: {data.intent}<br />
                                        Total Users: {data.total}
                                      </p>
                                    </div>
                                  );
                                }
                                return null;
                              }}
                            />
                            <Line type="monotone" dataKey="rate" stroke="#82ca9d" name="Intent Rate" strokeWidth={2} />
                          </LineChart>
                        </ResponsiveContainer>
                      )}
                    </Card>
                  </Col>
                </Row>


              </Spin>
            )}

            <Card title="User List" extra={<Button icon={<ReloadOutlined />} onClick={fetchUserData}>Refresh</Button>}>
              <Table
                dataSource={users}
                columns={columns}
                rowKey="_id"
                pagination={{
                  current: filters.page,
                  pageSize: filters.limit,
                  total: total,
                  showSizeChanger: true
                }}
                loading={loading}
                onChange={handleTableChange}
              />
            </Card>
          </Content>
        </Layout>

        {/* User Detail Drawer */}
        <Drawer
          title="User Profile Analysis"
          placement="right"
          width={640}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          loading={drawerLoading}
        >
          {selectedUser && (
            <>
              <Descriptions title="Basic Info" bordered column={1}>
                <Descriptions.Item label="Email">{selectedUser.user_email}</Descriptions.Item>
                <Descriptions.Item label="User Type">{selectedUser.ai_profile?.user_type}</Descriptions.Item>
                <Descriptions.Item label="Primary Purpose">{selectedUser.ai_profile?.primary_purpose}</Descriptions.Item>
                <Descriptions.Item label="Activity Level">{selectedUser.ai_profile?.activity_level}</Descriptions.Item>
                <Descriptions.Item label="Content Focus">
                  {selectedUser.ai_profile?.content_focus?.map(t => <Tag key={t}>{t}</Tag>)}
                </Descriptions.Item>
                <Descriptions.Item label="Payment Status">
                  {selectedUser.payment_stats?.is_paid_user ? <Tag color="gold">Paid User</Tag> : <Tag>Free User</Tag>}
                  {selectedUser.payment_stats?.has_payment_intent && <Tag color="orange">Has Intent</Tag>}
                </Descriptions.Item>
              </Descriptions>

              <div style={{ marginTop: 24 }}>
                <Title level={5}>Positioning</Title>
                <Space wrap>
                  <Tag color="blue">{selectedUser.ai_profile?.positioning?.industry}</Tag>
                  <Tag color="cyan">{selectedUser.ai_profile?.positioning?.business_scale}</Tag>
                  <Tag color="geekblue">{selectedUser.ai_profile?.positioning?.platform}</Tag>
                  <Tag color="purple">{selectedUser.ai_profile?.positioning?.content_type}</Tag>
                </Space>
              </div>

              <div style={{ marginTop: 24, background: '#f6ffed', padding: 16, borderRadius: 8, border: '1px solid #b7eb8f' }}>
                <Title level={5} style={{ color: '#389e0d' }}>Business Potential: {selectedUser.ai_profile?.business_potential?.score}/10</Title>
                <Descriptions column={1} size="small" contentStyle={{ color: '#135200' }} labelStyle={{ color: '#135200', fontWeight: 'bold' }}>
                  <Descriptions.Item label="Stage">{selectedUser.ai_profile?.business_potential?.stage}</Descriptions.Item>
                  <Descriptions.Item label="Recommendation">{selectedUser.ai_profile?.business_potential?.recommendation}</Descriptions.Item>
                  <Descriptions.Item label="Barrier">{selectedUser.ai_profile?.business_potential?.barrier}</Descriptions.Item>
                </Descriptions>
              </div>

              <div style={{ marginTop: 24 }}>
                <Title level={5}>Workflow Analysis</Title>
                <List
                  dataSource={selectedUser.ai_profile?.workflow_analysis}
                  renderItem={item => (
                    <List.Item>
                      <List.Item.Meta
                        avatar={<Badge count={item.rank} style={{ backgroundColor: '#1890ff' }} />}
                        title={
                          <Space>
                            {item.purpose}
                            <Tag color={item.confidence === '高' ? 'green' : 'orange'}>{item.confidence}</Tag>
                          </Space>
                        }
                        description={item.reason}
                      />
                    </List.Item>
                  )}
                />
              </div>
              <div style={{ marginTop: 24 }}>
                <Title level={5}>Summary</Title>
                <div style={{ fontStyle: 'italic', color: '#8c8c8c' }}>
                  "{selectedUser.ai_profile?.summary}"
                </div>
              </div>

              {selectedUser.top_workflows?.length > 0 && (
                <div style={{ marginTop: 24 }}>
                  <Title level={5}>Top Workflows</Title>
                  <List
                    itemLayout="vertical"
                    dataSource={selectedUser.top_workflows}
                    renderItem={item => {
                      // Logic to fallback for name and node types
                      const displayName = item.workflow_name || (item.flow_id ? `Workflow (${item.flow_id.slice(-6)})` : `Workflow #${item.rank}`);

                      let displayNodeTypes = item.node_types || [];
                      if (displayNodeTypes.length === 0 && item.topology?.nodes) {
                        // Extract unique types from topology
                        displayNodeTypes = Array.from(new Set(item.topology.nodes.map(n => n.type)));
                      }

                      return (
                        <List.Item
                          extra={
                            item.snapshot_url && (
                              <img
                                width={100}
                                alt="snapshot"
                                src={item.snapshot_url}
                                style={{ borderRadius: 8, objectFit: 'cover' }}
                              />
                            )
                          }
                        >
                          <List.Item.Meta
                            avatar={<Badge count={item.rank} color="#722ed1" />}
                            title={
                              <Space>
                                {displayName}
                                <Tag color="cyan">Runs: {item.run_count}</Tag>
                              </Space>
                            }
                            description={
                              <Space direction="vertical" size={2}>
                                {displayNodeTypes.length > 0 ? (
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    Nodes: {displayNodeTypes.slice(0, 5).join(', ')}
                                    {displayNodeTypes.length > 5 && '...'}
                                  </Text>
                                ) : <Text type="secondary" style={{ fontSize: 12 }}>Nodes: N/A</Text>}

                                {item.flow_id && <Text copyable={{ text: item.flow_id }} style={{ fontSize: 10, color: '#bfbfbf' }}>ID: {item.flow_id}</Text>}
                              </Space>
                            }
                          />
                        </List.Item>
                      );
                    }}
                  />
                </div>
              )}
            </>
          )}
        </Drawer>
      </Layout>
    </ConfigProvider>
  );
};

export default App;
