import React, { useState, useEffect } from 'react';
import {
  Layout, Table, Tag, Space, Card, Statistic, Row, Col,
  Form, Select, Slider, Button, Drawer, Typography, Descriptions,
  List, Badge, ConfigProvider, theme
} from 'antd';
import {
  UserOutlined, DashboardOutlined, FilterOutlined,
  ReloadOutlined, RiseOutlined, RocketTwoTone, ArrowLeftOutlined,
  PlayCircleTwoTone, CheckCircleTwoTone
} from '@ant-design/icons';
import { getUsers, getStats, getFilters, getUser } from './services/api';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;
const { Option } = Select;

const App = () => {
  // State
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [filterOptions, setFilterOptions] = useState({});
  const [filters, setFilters] = useState({ page: 1, limit: 10, min_score: 1 });

  // Drawer State
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);

  // Initial Load
  useEffect(() => {
    loadInitData();
  }, []);

  // Reload users when filters change
  useEffect(() => {
    fetchUserData();
  }, [filters]);

  const loadInitData = async () => {
    try {
      const [s, f] = await Promise.all([getStats(), getFilters()]);
      setStats(s);
      setFilterOptions(f);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchUserData = async () => {
    setLoading(true);
    try {
      const data = await getUsers(filters);
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
      title: 'Total Runs (30d)',
      dataIndex: ['stats', 'total_runs_30d'],
      key: 'stats.total_runs_30d',
      sorter: true,
      render: (val) => val || 0
    },
    {
      title: 'Active Days (30d)',
      dataIndex: ['stats', 'active_days_30d'],
      key: 'stats.active_days_30d',
      sorter: true,
      render: (val) => `${val} days`
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
            style={{
              padding: '24px',
              background: 'rgba(255, 255, 255, 0.6)',
              backdropFilter: 'blur(20px)',
              borderRight: '1px solid rgba(0,0,0,0.03)'
            }}
          >
            <Title level={4} style={{ marginBottom: 24, fontWeight: 300 }}><FilterOutlined /> Filters</Title>
            <Form layout="vertical" onValuesChange={handleFilterChange}>
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
          </Sider>

          <Content style={{ padding: '24px', overflowY: 'auto', background: '#f5f7fa' }}>
            {/* Dashboard Stats */}
            {stats && (
              <>
                <Row gutter={16} style={{ marginBottom: '24px' }}>
                  <Col span={6}>
                    <Card hoverable>
                      <Statistic
                        title="Total Users"
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
                  <Col span={12}>
                    <Card
                      title={
                        selectedCategory ? (
                          <Space>
                            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => setSelectedCategory(null)} />
                            {selectedCategory}
                          </Space>
                        ) : "User Category Distribution"
                      }
                      extra={!selectedCategory && <Text type="secondary" style={{ fontSize: 12 }}>Click to drill-down</Text>}
                      style={{ height: 350 }}
                    >
                      {stats.categories ? (
                        <ResponsiveContainer width="100%" height={280}>
                          <PieChart>
                            <Pie
                              data={
                                selectedCategory && stats.categories[selectedCategory]
                                  ? Object.entries(stats.categories[selectedCategory].subcategories).map(([name, value]) => ({ name, value }))
                                  : Object.entries(stats.categories).map(([name, data]) => ({ name, value: data.count }))
                              }
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={100}
                              fill="#1890ff"
                              paddingAngle={5}
                              dataKey="value"
                              label
                              onClick={(data) => {
                                if (!selectedCategory) setSelectedCategory(data.name);
                              }}
                              style={{ cursor: !selectedCategory ? 'pointer' : 'default' }}
                            >
                              {(selectedCategory && stats.categories[selectedCategory]
                                ? Object.entries(stats.categories[selectedCategory].subcategories)
                                : Object.entries(stats.categories)
                              ).map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#EFDB50', '#ff85c0'][index % 7]} />
                              ))}
                            </Pie>
                            <Tooltip />
                            <Legend />
                          </PieChart>
                        </ResponsiveContainer>
                      ) : <Text type="secondary">No category data yet.</Text>}
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card title="Top Industries" style={{ height: 350 }}>
                      {stats.industries && (
                        <ResponsiveContainer width="100%" height={280}>
                          <BarChart
                            data={Object.entries(stats.industries).slice(0, 5).map(([name, value]) => ({ name, value }))}
                            layout="vertical"
                            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis type="number" />
                            <YAxis type="category" dataKey="name" width={100} />
                            <Tooltip />
                            <Bar dataKey="value" fill="#82ca9d" />
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </Card>
                  </Col>
                </Row>
              </>
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
                    renderItem={item => (
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
                              {item.workflow_name || "Unnamed Workflow"}
                              <Tag color="cyan">Runs: {item.run_count}</Tag>
                            </Space>
                          }
                          description={
                            <Space direction="vertical" size={2}>
                              <Text type="secondary" style={{ fontSize: 12 }}>Node Types: {item.node_types?.join(', ')}</Text>
                              <Text code style={{ fontSize: 10 }}>{item.signature}</Text>
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
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
